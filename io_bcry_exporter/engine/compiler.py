# ------------------------------------------------------------------------------
# Name:        engine/compiler.py
# Purpose:     Resource compiler transactions and background thread invocations
# ------------------------------------------------------------------------------

import fnmatch
import multiprocessing
import os
import shutil
import subprocess
import tempfile
import threading
from xml.dom.minidom import Document

import bpy

# Import modular package dependencies
from ..core import exceptions
from ..core.logger import bcPrint
from .. import utils


class RCInstance:
    """Manages background threads for compiling TIF textures and DAE geometries."""

    def __init__(self, config):
        self.__config = config

    def convert_tif(self, source_images):
        """Prepares images in the main thread, then spawns an RC background thread."""

        # 1. MAIN THREAD: Prepare images (save, invert) BEFORE starting the background thread
        # This completely avoids context/thread violations with the Blender API.
        tmp_dir = tempfile.mkdtemp("CryBlend")
        prepared_files = {}

        for image in source_images:
            if not image:
                continue

            try:
                # Determine paths
                original_path = image.filepath
                image_extension = utils.get_extension_from_path(original_path)

                # If it's already a TIF, just add it to the processing queue directly
                if image_extension.lower() == ".tif":
                    prepared_files[original_path] = original_path
                    continue

                tiff_image_path = utils.get_path_with_new_extension(
                    original_path, "tif"
                )
                temp_tiff_path = os.path.join(
                    tmp_dir, os.path.basename(tiff_image_path)
                )
                tiff_image_absolute_path = utils.get_absolute_path(tiff_image_path)

                # Check if green channel inversion is required (Normal maps)
                is_normal_map = "_ddn" in image.name
                temp_image = None

                if is_normal_map:
                    # Create a copy in memory to avoid altering the original in the scene
                    temp_image = image.copy()
                    self._invert_green_channel_safe(temp_image)
                    img_to_save = temp_image
                else:
                    img_to_save = image

                # Save as a temporary TIF
                img_to_save.filepath_raw = temp_tiff_path
                img_to_save.file_format = "TIFF"
                img_to_save.save()

                # Restore original paths
                if not is_normal_map:
                    img_to_save.filepath = original_path

                # Remove the temporary copy from Blender's memory if one was created
                if temp_image:
                    bpy.data.images.remove(temp_image)

                # Map temporary path to the final destination path
                prepared_files[temp_tiff_path] = tiff_image_absolute_path

            except Exception as e:
                bcPrint(f"Failed to prepare image {image.name} for RC: {e}", "warning")

        # 2. BACKGROUND THREAD: Pass only disk paths (Blender API is no longer used here)
        if prepared_files:
            converter = _TIFConverter(self.__config, prepared_files, tmp_dir)
            conversion_thread = threading.Thread(target=converter)
            conversion_thread.start()

    def _invert_green_channel_safe(self, image):
        """Fast G-channel inversion without using bpy.ops (Safe for all contexts)."""
        if not image.pixels:
            return

        import numpy as np

        # Load pixels into numpy array (format: R, G, B, A, R, G, B, A...)
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)

        # Invert every second element (G channel), starting from index 1, step 4
        pixels[1::4] = 1.0 - pixels[1::4]

        # Push pixels back to the image
        image.pixels.foreach_set(pixels)
        image.update()

    def convert_dae(self, source):
        """Evaluates file paths in the main thread before dispatching the DAE background worker."""
        filepath = bpy.path.ensure_ext(self.__config.filepath, ".dae")
        dae_path = utils.get_absolute_path_for_rc(filepath)

        converter = _DAEConverter(self.__config, source, filepath, dae_path)
        conversion_thread = threading.Thread(target=converter)
        conversion_thread.start()


class _DAEConverter:
    """Handles the writing of DAE files and calls rc.exe to compile assets."""

    def __init__(self, config, source, filepath, dae_path):
        self.__config = config
        self.__doc = source
        self.__filepath = filepath
        self.__dae_path = dae_path

    def __call__(self):
        # Write the collada document to disk
        utils.generate_xml(self.__filepath, self.__doc, overwrite=True)

        if not self.__config.disable_rc:
            rc_params = [
                "/verbose",
                f"/threads={multiprocessing.cpu_count()}",
                "/refresh",
            ]
            if self.__config.vcloth_pre_process:
                rc_params.append("/wait=0 /forceVCloth")

            rc_process = run_rc(self.__config.rc_path, self.__dae_path, rc_params)

            if rc_process is not None:
                rc_process.wait()

                if not self.__config.is_animation_process:
                    self.__recompile(self.__dae_path)
                else:
                    self.__rename_anm_files(self.__dae_path)

        if self.__config.make_layer:
            lyr_contents = self.__make_layer()
            lyr_path = os.path.splitext(self.__filepath)[0] + ".lyr"
            utils.generate_file(lyr_path, lyr_contents)

        if not self.__config.save_dae:
            rcdone_path = f"{self.__dae_path}.rcdone"
            utils.remove_file(self.__dae_path)
            utils.remove_file(rcdone_path)

    def __recompile(self, dae_path):
        # Skip the second pass for older Resource Compilers (Crysis 2 / CE3)
        if getattr(self.__config, "legacy_rc", False):
            return

        output_path = os.path.dirname(dae_path)
        ALLOWED_NODE_TYPES = ("chr", "skin")
        for group in utils.get_export_nodes():
            node_type = utils.get_node_type(group)
            if node_type in ALLOWED_NODE_TYPES:
                out_file = os.path.join(output_path, group.name)
                args = [
                    self.__config.rc_path,
                    "/refresh",
                    "/vertexindexformat=u16",
                    out_file,
                ]
                subprocess.Popen(args)
            elif node_type == "i_caf":
                try:
                    caf_path = os.path.join(output_path, ".caf")
                    anim_settings_path = os.path.join(output_path, ".animsettings")
                    alt_anim_settings_path = os.path.join(output_path, ".$animsettings")

                    if os.path.exists(caf_path):
                        os.remove(caf_path)
                    if os.path.exists(anim_settings_path):
                        os.remove(anim_settings_path)
                    if os.path.exists(alt_anim_settings_path):
                        os.remove(alt_anim_settings_path)
                except OSError as e:
                    bcPrint(
                        f"Failed to clean up temporary animation files: {e}", "warning"
                    )

    def __rename_anm_files(self, dae_path):
        output_path = os.path.dirname(dae_path)

        for collection in utils.get_export_nodes():
            if utils.get_node_type(collection) == "anm":
                node_name = utils.get_node_name(collection)
                src_name = f"{node_name}_{collection.name}"
                src_name = os.path.join(output_path, src_name)
                src_cryasset_name = "{}_{}".format(
                    node_name, collection.name + ".cryasset"
                )
                src_cryasset_name = os.path.join(output_path, src_cryasset_name)

                if os.path.exists(src_name):
                    dest_name = utils.get_geometry_animation_file_name(collection)
                    dest_name = os.path.join(output_path, dest_name)
                    dest_cryasset_name = utils.get_cryasset_animation_file_name(
                        collection
                    )
                    dest_cryasset_name = os.path.join(output_path, dest_cryasset_name)

                    if os.path.exists(dest_name):
                        os.remove(dest_name)
                        os.remove(dest_cryasset_name)

                    os.rename(src_name, dest_name)
                    os.rename(src_cryasset_name, dest_cryasset_name)

    def __get_mtl_files_in_directory(self, directory):
        MTL_MATCH_STRING = "*.{!s}".format("mtl")

        mtl_files = []
        for file in os.listdir(directory):
            if fnmatch.fnmatch(file, MTL_MATCH_STRING):
                filepath = f"{directory!s}/{file!s}"
                mtl_files.append(filepath)

        return mtl_files

    def _create_attributes(self, node_name, attributes):
        doc = Document()
        node = doc.createElement(node_name)
        for name, value in attributes.items():
            node.setAttribute(name, value)

        return node

    def __make_layer(self):
        layer_doc = Document()
        object_layer = layer_doc.createElement("ObjectLayer")
        layer_name = "ExportedLayer"
        layer = self._create_attributes(
            "Layer",
            {
                "name": layer_name,
                "GUID": utils.get_guid(),
                "FullName": layer_name,
                "External": "0",
                "Exportable": "1",
                "ExportLayerPak": "1",
                "DefaultLoaded": "0",
                "HavePhysics": "1",
                "Expanded": "0",
                "IsDefaultColor": "1",
            },
        )

        layer_objects = layer_doc.createElement("LayerObjects")
        for group in utils.get_export_nodes():
            if len(group.objects) > 1:
                origin = 0, 0, 0
                rotation = 1, 0, 0, 0
            else:
                origin = group.objects[0].location
                rotation = group.objects[0].delta_rotation_quaternion

            object_node = self._create_attributes(
                "Object",
                {
                    "name": group.name[14:],
                    "Type": "Entity",
                    "Id": utils.get_guid(),
                    "LayerGUID": layer.getAttribute("GUID"),
                    "Layer": layer_name,
                    "Pos": "{}, {}, {}".format(*origin[:]),
                    "Rotate": "{}, {}, {}, {}".format(*rotation[:]),
                    "EntityClass": "BasicEntity",
                    "FloorNumber": "-1",
                    "RenderNearest": "0",
                    "NoStaticDecals": "0",
                    "CreatedThroughPool": "0",
                    "MatLayersMask": "0",
                    "OutdoorOnly": "0",
                    "CastShadow": "1",
                    "MotionBlurMultiplier": "1",
                    "LodRatio": "100",
                    "ViewDistRatio": "100",
                    "HiddenInGame": "0",
                },
            )
            properties = self._create_attributes(
                "Properties",
                {
                    "object_Model": f"/Objects/{group.name[14:]}.cgf",
                    "bCanTriggerAreas": "0",
                    "bExcludeCover": "0",
                    "DmgFactorWhenCollidingAI": "1",
                    "esFaction": "",
                    "bHeavyObject": "0",
                    "bInteractLargeObject": "0",
                    "bMissionCritical": "0",
                    "bPickable": "0",
                    "soclasses_SmartObjectClass": "",
                    "bUsable": "0",
                    "UseMessage": "0",
                },
            )
            health = self._create_attributes(
                "Health",
                {
                    "bInvulnerable": "1",
                    "MaxHealth": "500",
                    "bOnlyEnemyFire": "1",
                },
            )
            interest = self._create_attributes(
                "Interest",
                {
                    "soaction_Action": "",
                    "bInteresting": "0",
                    "InterestLevel": "1",
                    "Pause": "15",
                    "Radius": "20",
                    "bShared": "0",
                },
            )
            vOffset = self._create_attributes(
                "vOffset",
                {
                    "x": "0",
                    "y": "0",
                    "z": "0",
                },
            )

            interest.appendChild(vOffset)
            properties.appendChild(health)
            properties.appendChild(interest)
            object_node.appendChild(properties)
            layer_objects.appendChild(object_node)

        layer.appendChild(layer_objects)
        object_layer.appendChild(layer)
        layer_doc.appendChild(object_layer)

        return layer_doc.toprettyxml(indent="    ")


class _TIFConverter:
    """Triggers RC in a background thread to produce DDS files using pre-processed TIF paths."""

    def __init__(self, config, prepared_files, tmp_dir):
        self.__config = config
        self.__prepared_files = prepared_files
        self.__tmp_dir = tmp_dir

    def __call__(self):
        # WARNING: No bpy.* calls here! Fully safe for background threading.
        for tmp_image_path, dest_image_path in self.__prepared_files.items():
            rc_params = self.__get_rc_params(dest_image_path)
            tiff_image_for_rc = utils.get_absolute_path_for_rc(tmp_image_path)

            bcPrint(tiff_image_for_rc)

            # Trigger external compiler
            rc_process = run_rc(
                self.__config.texture_rc_path, tiff_image_for_rc, rc_params
            )

            rc_process.wait()

        if self.__config.texture_rc_path:
            self.__save_tiffs()

        self.__remove_tmp_files()

    def __get_rc_params(self, destination_path):
        rc_params = [
            "/verbose",
            f"/threads={multiprocessing.cpu_count()}",
            "/refresh",
        ]

        image_directory = os.path.dirname(
            utils.get_absolute_path_for_rc(destination_path)
        )
        rc_params.append(f"/targetroot={image_directory!s}")

        return rc_params

    def __save_tiffs(self):
        for tmp_image, dest_image in self.__prepared_files.items():
            # Skip if paths match (image was already a TIF)
            if tmp_image == dest_image:
                continue
            bcPrint(f"Moving tmp image: {tmp_image!r} to {dest_image!r}", "debug")
            try:
                shutil.move(tmp_image, dest_image)
            except Exception as e:
                bcPrint(f"Failed to move TIF: {e}", "warning")

    def __remove_tmp_files(self):
        for tmp_image in self.__prepared_files.keys():
            try:
                if os.path.exists(tmp_image) and self.__tmp_dir in tmp_image:
                    bcPrint(f"Removing tmp image: {tmp_image!r}", "debug")
                    os.remove(tmp_image)
            except OSError:
                pass

        try:
            if os.path.exists(self.__tmp_dir):
                os.removedirs(self.__tmp_dir)
        except OSError:
            pass
        self.__prepared_files.clear()


def run_rc(rc_path, files_to_process, params=None):
    """Executes the external CryEngine Resource Compiler subprocess."""
    bcPrint(f"RC Path: {os.path.abspath(rc_path)}", newline=True)
    process_params = [rc_path]

    if isinstance(files_to_process, list):
        process_params.extend(files_to_process)
    else:
        process_params.append(files_to_process)

    process_params.extend(params)

    bcPrint(f"RC Parameters: {params}")
    bcPrint(f"Processing File: {files_to_process}")

    rc_dir = os.path.dirname(os.path.abspath(rc_path))

    try:
        run_object = subprocess.Popen(process_params, cwd=rc_dir)
    except (FileNotFoundError, OSError) as e:
        bcPrint(f"Failed to execute Resource Compiler: {e}", "error")
        raise exceptions.NoRcSelectedException()

    print()
    return run_object
