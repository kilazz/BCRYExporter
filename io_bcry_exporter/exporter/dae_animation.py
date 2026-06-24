# ------------------------------------------------------------------------------
# Name:        exporter/dae_animation.py
# Purpose:     COLLADA skeletal animation tracks and timeline range compiler
# ------------------------------------------------------------------------------

import os
import bpy

# Modular package imports
from ..core.logger import bcPrint
from ..core import exceptions
from ..engine.compiler import RCInstance
from .. import utils
from .dae_geometry import CrytekDaeExporter

# Mappings of axes indexes used by F-Curves
AXES = {
    "X": 0,
    "Y": 1,
    "Z": 2,
}


class CrytekDaeAnimationExporter(CrytekDaeExporter):
    """COLLADA Exporter class specializing in skeletal joint keyframe animation tracks."""

    def __init__(self, config):
        super().__init__(config)

    def export(self):
        """Prepares and compiles skeletal keyframe ranges into external animation tracks."""
        self._prepare_for_export()

        root_element = self._doc.createElement("collada")
        root_element.setAttribute(
            "xmlns", "http://www.collada.org/2005/11/COLLADASchema"
        )
        root_element.setAttribute("version", "1.4.1")
        self._doc.appendChild(root_element)
        self._create_file_header(root_element)

        libanmcl = self._doc.createElement("library_animation_clips")
        libanm = self._doc.createElement("library_animations")
        root_element.appendChild(libanmcl)
        root_element.appendChild(libanm)

        lib_visual_scene = self._doc.createElement("library_visual_scenes")
        visual_scene = self._doc.createElement("visual_scene")
        visual_scene.setAttribute("id", "scene")
        visual_scene.setAttribute("name", "scene")
        lib_visual_scene.appendChild(visual_scene)
        root_element.appendChild(lib_visual_scene)

        # Back up active workspace timeline frames
        initial_frame_active = bpy.context.scene.frame_current
        initial_frame_start = bpy.context.scene.frame_start
        initial_frame_end = bpy.context.scene.frame_end

        ALLOWED_NODE_TYPES = ("i_caf", "anm")
        for group in utils.get_animation_export_nodes():
            node_type = utils.get_node_type(group)
            node_name = utils.get_node_name(group)

            if node_type in ALLOWED_NODE_TYPES:
                object_ = None
                layers = None

                if node_type == "i_caf":
                    object_ = utils.get_armature_from_node(group)
                    layers = utils.activate_all_bone_layers(object_)
                elif node_type == "anm":
                    object_ = group.objects[0]

                # Extract animation frame bounds (either custom props, markers, or timeline)
                frame_start, frame_end = utils.get_animation_node_range(
                    object_, node_name, initial_frame_start, initial_frame_end
                )
                bpy.context.scene.frame_start = frame_start
                bpy.context.scene.frame_end = frame_end

                print("")
                bcPrint(f"Processing animation node: {group.name}")
                bcPrint(f"Export frame range: [{frame_start} - {frame_end}]")

                if node_type == "i_caf":
                    utils.add_fakebones(group)
                try:
                    self._export_library_animation_clips_and_animations(
                        libanmcl, libanm, group
                    )
                    # Inherited visual scene writer parses the node cleanly
                    self._export_library_visual_scenes(visual_scene)
                except RuntimeError as e:
                    bcPrint(f"Skeletal animation compilation skipped: {e}", "warning")
                finally:
                    if node_type == "i_caf":
                        utils.remove_fakebones()
                        utils.recover_bone_layers(object_, layers)

                    bcPrint("Animation track generated.")

        # Restore original workspace frames
        bpy.context.scene.frame_current = initial_frame_active
        bpy.context.scene.frame_start = initial_frame_start
        bpy.context.scene.frame_end = initial_frame_end
        print("")

        self._export_scene(root_element)

        # Trigger RC compiler background thread
        converter = RCInstance(self._config)
        converter.convert_dae(self._doc)

    def _prepare_for_export(self):
        """Sanitizes names prior to animation tracks evaluation."""
        utils.clean_file()

    # ------------------------------------------------------------------------------
    # Library Animations & Clips
    # ------------------------------------------------------------------------------

    def _export_library_animation_clips_and_animations(self, libanmcl, libanm, group):
        """Assembles animation clips linking target bone animation samplers."""
        scene = bpy.context.scene
        anim_id = utils.get_animation_id(group)

        animation_clip = self._doc.createElement("animation_clip")
        animation_clip.setAttribute("id", anim_id)
        animation_clip.setAttribute(
            "start", f"{utils.frame_to_time(scene.frame_start):f}"
        )
        animation_clip.setAttribute("end", f"{utils.frame_to_time(scene.frame_end):f}")
        is_animation = False

        for object_ in group.objects:
            if (
                object_.type != "ARMATURE"
                and object_.animation_data
                and object_.animation_data.action
            ):
                is_animation = True
                bone_name = self._get_dae_bone_name(object_, group)

                for axis in iter(AXES):
                    animation = self._get_animation_location(
                        object_, bone_name, axis, anim_id
                    )
                    if animation is not None:
                        libanm.appendChild(animation)

                for axis in iter(AXES):
                    animation = self._get_animation_rotation(
                        object_, bone_name, axis, anim_id
                    )
                    if animation is not None:
                        libanm.appendChild(animation)

                self._export_instance_animation_parameters(
                    object_, animation_clip, anim_id
                )

        if is_animation:
            libanmcl.appendChild(animation_clip)

    def _export_instance_animation_parameters(self, object_, animation_clip, anim_id):
        """Binds location and rotation parameters inside the clip node."""
        location_exists = rotation_exists = False
        for curve in object_.animation_data.action.fcurves:
            for axis in iter(AXES):
                if curve.array_index == AXES[axis]:
                    if curve.data_path == "location":
                        location_exists = True
                    if curve.data_path == "rotation_euler":
                        rotation_exists = True
                    if location_exists and rotation_exists:
                        break

        if location_exists:
            self._export_instance_parameter(
                object_, animation_clip, "location", anim_id
            )
        if rotation_exists:
            self._export_instance_parameter(
                object_, animation_clip, "rotation_euler", anim_id
            )

    def _export_instance_parameter(self, object_, animation_clip, parameter, anim_id):
        """Constructs <instance_animation> bindings linking f-curve parameters."""
        for axis in iter(AXES):
            inst = self._doc.createElement("instance_animation")
            inst.setAttribute(
                "url",
                f"#{anim_id!s}-{object_.name!s}_{parameter!s}_{axis!s}",
            )
            animation_clip.appendChild(inst)

    def _get_animation_location(self, object_, bone_name, axis, anim_id):
        """Extracts location keys for a single coordinates axis."""
        attribute_type = "location"
        multiplier = 1
        target = "{!s}{!s}{!s}".format(bone_name, "/translation.", axis)

        animation_element = self._get_animation_attribute(
            object_, axis, attribute_type, multiplier, target, anim_id
        )
        return animation_element

    def _get_animation_rotation(self, object_, bone_name, axis, anim_id):
        """Extracts rotation euler keys, converting radians to degrees."""
        attribute_type = "rotation_euler"
        multiplier = utils.to_degrees
        target = "{!s}{!s}{!s}{!s}".format(bone_name, "/rotation_", axis, ".ANGLE")

        animation_element = self._get_animation_attribute(
            object_, axis, attribute_type, multiplier, target, anim_id
        )
        return animation_element

    def _get_animation_attribute(
        self, object_, axis, attribute_type, multiplier, target, anim_id
    ):
        """Iterates through F-Curve keyframes, building interpolator nodes and source lists."""
        id_prefix = f"{anim_id!s}-{object_.name!s}_{attribute_type!s}_{axis!s}"
        source_prefix = f"#{id_prefix!s}"

        for curve in object_.animation_data.action.fcurves:
            if curve.data_path == attribute_type and curve.array_index == AXES[axis]:
                keyframe_points = curve.keyframe_points
                sources = {
                    "input": [],
                    "output": [],
                    "interpolation": [],
                    "intangent": [],
                    "outangent": [],
                }
                for keyframe_point in keyframe_points:
                    khlx = keyframe_point.handle_left[0]
                    khly = keyframe_point.handle_left[1]
                    khrx = keyframe_point.handle_right[0]
                    khry = keyframe_point.handle_right[1]
                    frame, value = keyframe_point.co

                    sources["input"].append(utils.frame_to_time(frame))
                    sources["output"].append(value * multiplier)
                    sources["interpolation"].append(keyframe_point.interpolation)
                    sources["intangent"].extend([utils.frame_to_time(khlx), khly])
                    sources["outangent"].extend([utils.frame_to_time(khrx), khry])

                animation_element = self._doc.createElement("animation")
                animation_element.setAttribute("id", id_prefix)

                for type_, data in sources.items():
                    anim_node = self._create_animation_node(type_, data, id_prefix)
                    animation_element.appendChild(anim_node)

                sampler = self._create_sampler(id_prefix, source_prefix)
                channel = self._doc.createElement("channel")
                channel.setAttribute("source", f"{source_prefix!s}-sampler")
                channel.setAttribute("target", target)

                animation_element.appendChild(sampler)
                animation_element.appendChild(channel)

                return animation_element

    def _create_animation_node(self, type_, data, id_prefix):
        """Assembles standard COLLADA sources representing animation curves."""
        id_ = f"{id_prefix!s}-{type_!s}"
        type_map = {
            "input": ["float", ["TIME"]],
            "output": ["float", ["VALUE"]],
            "intangent": ["float", "XY"],
            "outangent": ["float", "XY"],
            "interpolation": ["name", ["INTERPOLATION"]],
        }

        # Optimized XML write source helper
        source = utils.write_source(id_, type_map[type_][0], data, type_map[type_][1])
        return source

    def _create_sampler(self, id_prefix, source_prefix):
        """Generates standard curve samplers linking tangents and interpolation types."""
        sampler = self._doc.createElement("sampler")
        sampler.setAttribute("id", f"{id_prefix!s}-sampler")

        input_node = self._doc.createElement("input")
        input_node.setAttribute("semantic", "INPUT")
        input_node.setAttribute("source", f"{source_prefix!s}-input")

        output_node = self._doc.createElement("input")
        output_node.setAttribute("semantic", "OUTPUT")
        output_node.setAttribute("source", f"{source_prefix!s}-output")

        interpolation = self._doc.createElement("input")
        interpolation.setAttribute("semantic", "INTERPOLATION")
        interpolation.setAttribute("source", f"{source_prefix!s}-interpolation")

        intangent = self._doc.createElement("input")
        intangent.setAttribute("semantic", "IN_TANGENT")
        intangent.setAttribute("source", f"{source_prefix!s}-intangent")

        outangent = self._doc.createElement("input")
        outangent.setAttribute("semantic", "OUT_TANGENT")
        outangent.setAttribute("source", f"{source_prefix!s}-outangent")

        sampler.appendChild(input_node)
        sampler.appendChild(output_node)
        sampler.appendChild(interpolation)
        sampler.appendChild(intangent)
        sampler.appendChild(outangent)

        return sampler

    def _create_cryengine_extra(self, node):
        """Overridden CryEngine Extra block specific to skeletal tracks compiler."""
        extra = self._doc.createElement("extra")
        technique = self._doc.createElement("technique")
        technique.setAttribute("profile", "CryEngine")
        properties = self._doc.createElement("properties")

        node_type = utils.get_node_type(node)
        prop = self._doc.createTextNode(f"fileType={node_type}")
        properties.appendChild(prop)

        prop = self._doc.createTextNode("CustomExportPath=")
        properties.appendChild(prop)

        technique.appendChild(properties)

        if node.name[:6] == "_joint":
            # Joint helpers can be processed if necessary
            pass

        extra.appendChild(technique)
        extra.appendChild(self._create_xsi_profile(node))

        return extra


def save(config):
    """Skeletal animations compiler transaction wrapper."""
    if not config.disable_rc and not os.path.isfile(config.rc_path):
        raise exceptions.NoRcSelectedException()

    exporter = CrytekDaeAnimationExporter(config)
    exporter.export()
