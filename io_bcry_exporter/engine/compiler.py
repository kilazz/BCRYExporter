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

    def convert_tif(self, source):
        converter = _TIFConverter(self.__config, source)
        conversion_thread = threading.Thread(target=converter)
        conversion_thread.start()

    def convert_dae(self, source):
        # Safely evaluate file paths in the main thread before dispatching the background worker
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
    """Saves non-TIF files to temporary TIF format and triggers RC to produce DDS files."""

    def __init__(self, config, source):
        self.__config = config
        self.__images_to_convert = source
        self.__tmp_images = {}
        self.__tmp_dir = tempfile.mkdtemp("CryBlend")

    def __call__(self):
        for image in self.__images_to_convert:
            rc_params = self.__get_rc_params(image.filepath)
            tiff_image_path = self.__get_temp_tiff_image_path(image)

            tiff_image_for_rc = utils.get_absolute_path_for_rc(tiff_image_path)
            bcPrint(tiff_image_for_rc)

            try:
                self.__create_normal_texture(image)
            except Exception as e:
                bcPrint(f"Failed to invert green channel: {e}", "warning")

            rc_process = run_rc(
                self.__config.texture_rc_path, tiff_image_for_rc, rc_params
            )

            # Re-save the original image after running the RC to
            # prevent the original one from getting lost
            try:
                if "_ddn" in image.name:
                    image.save()
            except Exception as e:
                bcPrint(f"Failed to save original texture after RC run: {e}", "warning")

            rc_process.wait()

        if self.__config.texture_rc_path:
            self.__save_tiffs()

        self.__remove_tmp_files()

    def __create_normal_texture(self, image):
        if "_ddn" in image.name:
            # Make a copy to prevent editing the original image
            temp_normal_image = image.copy()
            self.__invert_green_channel(temp_normal_image)
            # Save to file and delete the temporary image
            new_normal_image_path = f"{os.path.splitext(temp_normal_image.filepath_raw)[0]}_cb_normal.{os.path.splitext(temp_normal_image.filepath_raw)[1]}"
            temp_normal_image.save_render(filepath=new_normal_image_path)
            bpy.data.images.remove(temp_normal_image)

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

    def __invert_green_channel(self, image):
        # NOTE: Modifying bpy data from background threads is inherently unsafe in Blender.
        # This remains unchanged for legacy compatibility, but ideally should be refactored
        # to the main thread in a future milestone.
        override = {"edit_image": bpy.data.images[image.name]}
        bpy.ops.image.invert(override, invert_g=True)
        image.update()

    def __get_temp_tiff_image_path(self, image):
        image_extension = utils.get_extension_from_path(image.filepath)
        bcPrint(image_extension)

        if ".tif" == image_extension:
            bcPrint(
                f"Image {image.name!r} is already a tif, not converting",
                "debug",
            )
            return image.filepath

        tiff_image_path = utils.get_path_with_new_extension(image.filepath, "tif")
        # Prepend our temp directory to isolate generated files safely
        temp_tiff_path = os.path.join(self.__tmp_dir, os.path.basename(tiff_image_path))
        tiff_image_absolute_path = utils.get_absolute_path(tiff_image_path)

        if tiff_image_path != image.filepath:
            self.__save_as_tiff(image, temp_tiff_path)
            self.__tmp_images[temp_tiff_path] = tiff_image_absolute_path

        return temp_tiff_path

    def __save_as_tiff(self, image, tiff_file_path):
        originalPath = image.filepath

        try:
            image.filepath_raw = tiff_file_path
            image.file_format = "TIFF"
            image.save()

        finally:
            image.filepath = originalPath

    def __save_tiffs(self):
        for tmp_image, dest_image in self.__tmp_images.items():
            bcPrint(f"Moving tmp image: {tmp_image!r} to {dest_image!r}", "debug")
            shutil.move(tmp_image, dest_image)

    def __remove_tmp_files(self):
        for tmp_image in self.__tmp_images:
            try:
                bcPrint(f"Removing tmp image: {tmp_image!r}", "debug")
                os.remove(tmp_image)
            except FileNotFoundError:
                pass

        os.removedirs(self.__tmp_dir)
        self.__tmp_images.clear()


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
