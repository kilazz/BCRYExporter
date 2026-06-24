# ------------------------------------------------------------------------------
# Name:        exporter/dae_base.py
# Purpose:     Base COLLADA exporter containing shared structures and writers
# ------------------------------------------------------------------------------

from datetime import datetime
from xml.dom.minidom import Document
import bpy

from .. import utils
from . import materials


class CrytekDaeExporterBase:
    """Base COLLADA/DAE Exporter class containing shared XML structures and boilerplate."""

    def __init__(self, config):
        self._config = config
        self._doc = Document()
        # Instantiate the material/texture exporter submodule
        self._m_exporter = materials.CrytekMaterialExporter(config)

    def _create_file_header(self, parent_element):
        """Assembles standard COLLADA metadata headers (<asset>)."""
        asset = self._doc.createElement("asset")
        parent_element.appendChild(asset)

        contributor = self._doc.createElement("contributor")
        asset.appendChild(contributor)

        author = self._doc.createElement("author")
        contributor.appendChild(author)
        author_name = self._doc.createTextNode("Blender User")
        author.appendChild(author_name)

        author_tool = self._doc.createElement("authoring_tool")
        author_name_text = self._doc.createTextNode(
            f"BCry v{self._config.bcry_version}"
        )
        author_tool.appendChild(author_name_text)
        contributor.appendChild(author_tool)

        created = self._doc.createElement("created")
        created_value = self._doc.createTextNode(datetime.now().isoformat(" "))
        created.appendChild(created_value)
        asset.appendChild(created)

        modified = self._doc.createElement("modified")
        asset.appendChild(modified)

        unit = self._doc.createElement("unit")
        unit.setAttribute("name", "meter")
        unit.setAttribute("meter", "1")
        asset.appendChild(unit)

        up_axis = self._doc.createElement("up_axis")
        z_up = self._doc.createTextNode("Z_UP")
        up_axis.appendChild(z_up)
        asset.appendChild(up_axis)

        # Write scene framerate to metadata so the Resource Compiler can parse tracks accurately
        scene_framerate = self._doc.createElement("scene_frame_rate")
        scene_framerate.setAttribute(
            "samples_per_second",
            f"{bpy.context.scene.render.fps / bpy.context.scene.render.fps_base:f}",
        )
        asset.appendChild(scene_framerate)

    def _export_library_cameras(self, root_element):
        """Generates the camera library element."""
        library_cameras = self._doc.createElement("library_cameras")
        root_element.appendChild(library_cameras)

    def _export_library_lights(self, root_element):
        """Generates the light library element."""
        library_lights = self._doc.createElement("library_lights")
        root_element.appendChild(library_lights)

    def _export_library_images(self, parent_element):
        """Generates the texture image references library."""
        library_images = self._doc.createElement("library_images")
        self._m_exporter.export_library_images(library_images)
        parent_element.appendChild(library_images)

    def _export_library_effects(self, parent_element):
        """Generates the Phong/Specular/Normal effects library."""
        library_effects = self._doc.createElement("library_effects")
        self._m_exporter.export_library_effects(library_effects)
        parent_element.appendChild(library_effects)

    def _export_library_materials(self, parent_element):
        """Generates the material parameters library linking back to effects."""
        library_materials = self._doc.createElement("library_materials")
        self._m_exporter.export_library_materials(library_materials)
        parent_element.appendChild(library_materials)

    def _export_scene(self, parent_element):
        """Finalizes the COLLADA XML output by binding the visual scene graph."""
        scene = self._doc.createElement("scene")
        instance_visual_scene = self._doc.createElement("instance_visual_scene")
        instance_visual_scene.setAttribute("url", "#scene")
        scene.appendChild(instance_visual_scene)
        parent_element.appendChild(scene)

    # ------------------------------------------------------------------------------
    # Transformation Utilities
    # ------------------------------------------------------------------------------

    def _write_transforms(self, object_, node):
        """Appends raw Translation, Rotation (XYZ), and Scale coordinates to visual scene nodes."""
        trans = self._create_translation_node(object_)
        rotx, roty, rotz = self._create_rotation_node(object_)
        scale = self._create_scale_node(object_)

        node.appendChild(trans)
        node.appendChild(rotx)
        node.appendChild(roty)
        node.appendChild(rotz)
        node.appendChild(scale)

    def _create_translation_node(self, object_):
        """Assembles <translate> XML element nodes."""
        trans = self._doc.createElement("translate")
        trans.setAttribute("sid", "translation")
        trans_text = self._doc.createTextNode(
            "{:f} {:f} {:f}".format(*object_.location)
        )
        trans.appendChild(trans_text)
        return trans

    def _create_rotation_node(self, object_):
        """Assembles <rotate> XML element nodes for standard XYZ axis orders."""
        rotz = self._write_rotation("z", "0 0 1 {:f}", object_.rotation_euler[2])
        roty = self._write_rotation("y", "0 1 0 {:f}", object_.rotation_euler[1])
        rotx = self._write_rotation("x", "1 0 0 {:f}", object_.rotation_euler[0])
        return rotz, roty, rotx

    def _write_rotation(self, axis, text_format, rotation):
        """Assembles single-axis <rotate> element instances converting radians to degrees."""
        rot = self._doc.createElement("rotate")
        rot.setAttribute("sid", f"rotation_{axis}")
        rot_text = self._doc.createTextNode(
            text_format.format(rotation * utils.to_degrees)
        )
        rot.appendChild(rot_text)
        return rot

    def _create_scale_node(self, object_):
        """Assembles <scale> XML element nodes."""
        scale = self._doc.createElement("scale")
        scale.setAttribute("sid", "scale")
        scale_text = self._doc.createTextNode(
            utils.floats_to_string(object_.scale, " ", "%s")
        )
        scale.appendChild(scale_text)
        return scale

    # ------------------------------------------------------------------------------
    # Bone Properties & Profiles
    # ------------------------------------------------------------------------------

    def _get_dae_bone_name(self, bone, group):
        """Resolves target XML bone naming schemas depending on legacy compatibility flag states."""
        if getattr(self._config, "legacy_rc", False):
            name = bone.name
            if name.startswith("Bip01"):
                ik_suffixes = [
                    "Hand2PistolPos",
                    "Hand2Pocket",
                    "Hand2RiflePos",
                    "Hand2Weapon",
                ]
                ik_types = ["IKBlend", "IKTarget"]
                is_ik = False
                matched_suffix = ""
                matched_type = ""
                for suffix in ik_suffixes:
                    if suffix in name:
                        for ik_type in ik_types:
                            if ik_type in name:
                                is_ik = True
                                matched_suffix = suffix
                                matched_type = ik_type
                                break
                        if is_ik:
                            break
                if is_ik:
                    side = (
                        "L"
                        if f"L{matched_suffix}" in name or f"L_{matched_suffix}" in name
                        else "R"
                    )
                    return f"Bip01_{side}{matched_suffix}_{matched_type}"
            return name.replace(" ", "_").replace("__", "_")
        else:
            props_name = self._create_properties_name(bone, group)
            return f"{bone.name.replace(' ', '_')!s}{props_name!s}"

    def _create_properties_name(self, bone, group):
        """Assembles BCRY custom bone properties used to map hierarchies inside modern RCs."""
        bone_name = bone.name.replace("__", "*")
        node_name = utils.get_node_name(group)
        return f"%{node_name!s}%--PRprops_name={bone_name!s}"

    def _create_xsi_profile(self, node):
        """Generates standard XSI profiles to preserve custom bone type metadata indices."""
        technique_xsi = self._doc.createElement("technique")
        technique_xsi.setAttribute("profile", "XSI")

        xsi_custom_p_set = self._doc.createElement("XSI_CustomPSet")
        xsi_custom_p_set.setAttribute("name", "ExportProperties")

        propagation = self._doc.createElement("propagation")
        propagation.appendChild(self._doc.createTextNode("NODE"))
        xsi_custom_p_set.appendChild(propagation)

        type_node = self._doc.createElement("type")
        type_node.appendChild(self._doc.createTextNode("CryExportNodeProperties"))
        xsi_custom_p_set.appendChild(type_node)

        xsi_parameter = self._doc.createElement("XSI_Parameter")
        xsi_parameter.setAttribute("id", "FileType")
        xsi_parameter.setAttribute("type", "Integer")
        xsi_parameter.setAttribute("value", utils.get_xsi_filetype_value(node))
        xsi_custom_p_set.appendChild(xsi_parameter)

        xsi_parameter = self._doc.createElement("XSI_Parameter")
        xsi_parameter.setAttribute("id", "Filename")
        xsi_parameter.setAttribute("type", "Text")
        xsi_parameter.setAttribute("value", utils.get_node_name(node))
        xsi_custom_p_set.appendChild(xsi_parameter)

        xsi_parameter = self._doc.createElement("XSI_Parameter")
        xsi_parameter.setAttribute("id", "Exportable")
        xsi_parameter.setAttribute("type", "Boolean")
        xsi_parameter.setAttribute("value", "1")
        xsi_custom_p_set.appendChild(xsi_parameter)

        xsi_parameter = self._doc.createElement("XSI_Parameter")
        xsi_parameter.setAttribute("id", "MergeObjects")
        xsi_parameter.setAttribute("type", "Boolean")
        xsi_parameter.setAttribute("value", str(int(self._config.merge_all_nodes)))
        xsi_custom_p_set.appendChild(xsi_parameter)

        technique_xsi.appendChild(xsi_custom_p_set)
        return technique_xsi

    # ------------------------------------------------------------------------------
    # Material Mappings
    # ------------------------------------------------------------------------------

    def _create_bind_material(self, object_):
        """Binds materials assigned to submesh slots within the visual scene node layout."""
        bind_material = self._doc.createElement("bind_material")
        technique_common = self._doc.createElement("technique_common")

        for material, materialname in self._m_exporter.get_materials_for_object(
            object_
        ).items():
            instance_material = self._doc.createElement("instance_material")
            instance_material.setAttribute("symbol", materialname)
            instance_material.setAttribute("target", f"#{materialname!s}")
            technique_common.appendChild(instance_material)

        bind_material.appendChild(technique_common)
        return bind_material
