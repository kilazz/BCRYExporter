# ------------------------------------------------------------------------------
# Name:        exporter/materials.py
# Purpose:     Material compiler, texture encoders, and CryEngine .mtl writers
# ------------------------------------------------------------------------------

import os
import re
from collections import OrderedDict
from xml.dom.minidom import Document

import bpy
from mathutils import Color

# Modular package imports
from ..core import exceptions
from ..core.logger import bcPrint
from ..engine.compiler import RCInstance
from .. import utils


class CrytekMaterialExporter:
    """Manages COLLADA XML material descriptions and maps texture dependencies."""

    def __init__(self, config):
        self._config = config
        self._doc = Document()
        self._materials = get_materials(config.export_selected_nodes)

    def generate_materials(self):
        """Triggers the automated write process for external CryEngine .mtl files."""
        generate_mtl_files(self._config, self._materials)

    def get_materials_for_object(self, object_):
        """Collects materials matched specifically to the active object's material slots."""
        materials = OrderedDict()
        for material_name, material in self._materials.items():
            for object_material in object_.data.materials:
                if object_material and material.name == object_material.name:
                    materials[material] = material_name

        return materials

    def export_library_images(self, library_images):
        """Assembles the COLLADA <library_images> element linking external engine textures."""
        images = []
        for node in utils.get_export_nodes():
            # Iterate over values() instead of keys to prevent string object crashes
            for material in self._materials.values():
                for image in get_textures(material):
                    if image:
                        images.append(image)

        self._write_texture_nodes(list(set(images)), library_images)

    def _write_texture_nodes(self, images, library_images):
        """Writes COLLADA XML image nodes and initiates asynchronous DDS conversion passes."""
        for image in images:
            image_node = self._doc.createElement("image")
            image_node.setAttribute("id", image.name)
            image_node.setAttribute("name", image.name)

            init_form = self._doc.createElement("init_from")
            path = get_image_path_for_game(image, self._config.game_dir)
            path_node = self._doc.createTextNode(path)
            init_form.appendChild(path_node)
            image_node.appendChild(init_form)
            library_images.appendChild(image_node)

        if self._config.convert_textures:
            convert_image_to_dds(images, self._config)

    def export_library_effects(self, library_effects):
        """Assembles standard COLLADA Phong-effects elements for active material profiles."""
        for material_name, material in self._materials.items():
            self._export_library_effects_material(
                material, material_name, library_effects
            )

    def _export_library_effects_material(
        self, material, material_name, library_effects
    ):
        images = get_textures(material)

        effect_node = self._doc.createElement("effect")
        effect_node.setAttribute("id", f"{material_name}_fx")
        profile_node = self._doc.createElement("profile_COMMON")
        self._write_surface_and_sampler(images, profile_node)

        technique_common = self._doc.createElement("technique")
        technique_common.setAttribute("sid", "common")

        self._write_phong_node(material, images, technique_common)
        profile_node.appendChild(technique_common)

        extra = self._create_double_sided_extra("GOOGLEEARTH")
        profile_node.appendChild(extra)
        effect_node.appendChild(profile_node)

        extra = self._create_double_sided_extra("MAX3D")
        effect_node.appendChild(extra)
        library_effects.appendChild(effect_node)

    def _write_surface_and_sampler(self, images, profile_node):
        """Defines surface parameters and 2D texture samplers inside the XML DOM tree."""
        for image in images:
            if image is None:
                continue

            surface = self._doc.createElement("newparam")
            surface.setAttribute("sid", f"{image.name}-surface")
            surface_node = self._doc.createElement("surface")
            surface_node.setAttribute("type", "2D")

            init_from_node = self._doc.createElement("init_from")
            temp_node = self._doc.createTextNode(image.name)
            init_from_node.appendChild(temp_node)
            surface_node.appendChild(init_from_node)
            surface.appendChild(surface_node)

            sampler = self._doc.createElement("newparam")
            sampler.setAttribute("sid", f"{image.name}-sampler")
            sampler_node = self._doc.createElement("sampler2D")

            source_node = self._doc.createElement("source")
            temp_node = self._doc.createTextNode(f"{image.name}-surface")
            source_node.appendChild(temp_node)
            sampler_node.appendChild(source_node)
            sampler.appendChild(sampler_node)

            profile_node.appendChild(surface)
            profile_node.appendChild(sampler)

    def _write_phong_node(self, material, images, parent_node):
        """Assembles standard Phong geometric lighting nodes mapping textures to shaders."""
        phong = self._doc.createElement("phong")

        emission = self._create_color_node(material, "emission")
        ambient = self._create_color_node(material, "ambient")

        if images[0]:
            diffuse = self._create_texture_node(images[0].name, "diffuse")
        else:
            diffuse = self._create_color_node(material, "diffuse")

        if images[1]:
            specular = self._create_texture_node(images[1].name, "specular")
        else:
            specular = self._create_color_node(material, "specular")

        shininess = self._create_attribute_node(material, "shininess")
        index_refraction = self._create_attribute_node(material, "index_refraction")

        phong.appendChild(emission)
        phong.appendChild(ambient)
        phong.appendChild(diffuse)
        phong.appendChild(specular)
        phong.appendChild(shininess)
        phong.appendChild(index_refraction)

        if images[2]:
            normal = self._create_texture_node(images[2].name, "normal")
            phong.appendChild(normal)

        parent_node.appendChild(phong)

    def _create_color_node(self, material, type_):
        """Appends color nodes to shader parameters."""
        node = self._doc.createElement(type_)
        color = self._doc.createElement("color")
        color.setAttribute("sid", type_)
        col = get_material_color(material, type_)
        color_text = self._doc.createTextNode(str(col))
        color.appendChild(color_text)
        node.appendChild(color)
        return node

    def _create_texture_node(self, image_name, type_):
        """Appends active texture parameters to shader layouts."""
        node = self._doc.createElement(type_)
        texture = self._doc.createElement("texture")
        texture.setAttribute("texture", f"{image_name}-sampler")
        node.appendChild(texture)
        return node

    def _create_attribute_node(self, material, type_):
        """Appends numeric float values to shader structures."""
        node = self._doc.createElement(type_)
        float_node = self._doc.createElement("float")
        float_node.setAttribute("sid", type_)
        val = get_material_attribute(material, type_)
        value = self._doc.createTextNode(val)
        float_node.appendChild(value)
        node.appendChild(float_node)
        return node

    def _create_double_sided_extra(self, profile):
        """Forces double-sided rendering parameters inside target profile structures."""
        extra = self._doc.createElement("extra")
        technique = self._doc.createElement("technique")
        technique.setAttribute("profile", profile)

        double_sided = self._doc.createElement("double_sided")
        double_sided_value = self._doc.createTextNode("1")
        double_sided.appendChild(double_sided_value)

        technique.appendChild(double_sided)
        extra.appendChild(technique)
        return extra

    def export_library_materials(self, library_materials):
        """Assembles standard COLLADA <library_materials> elements linking back to effects."""
        for material_name, material in self._materials.items():
            material_element = self._doc.createElement("material")
            material_element.setAttribute("id", material_name)

            instance_effect = self._doc.createElement("instance_effect")
            instance_effect.setAttribute("url", f"#{material_name}_fx")
            material_element.appendChild(instance_effect)
            library_materials.appendChild(material_element)


# ------------------------------------------------------------------------------
# Material Utils & Helper Functions (Formerly material_utils.py)
# ------------------------------------------------------------------------------


def generate_mtl_files(config, materials=None):
    """Generates the actual custom XML files representing CryEngine material templates (.mtl)."""
    if materials is None:
        materials = get_materials(config.export_selected_nodes)

    for node in get_material_groups(materials):
        doc = Document()
        parent_material = doc.createElement("Material")
        parent_material.setAttribute("MtlFlags", "524544")
        parent_material.setAttribute("vertModifType", "0")

        sub_material = doc.createElement("SubMaterials")
        parent_material.appendChild(sub_material)
        set_public_params(doc, None, parent_material)

        print()
        bcPrint(f"'{node}' material is being processed...")

        for material_name, material in materials.items():
            if material_name.split("__")[0] != node:
                continue

            print()
            write_material_information(material_name)

            material_node = doc.createElement("Material")
            set_material_attributes(material, material_name, material_node)
            add_textures(doc, material, material_node, config)
            set_public_params(doc, material, material_node)

            sub_material.appendChild(material_node)

        doc.appendChild(parent_material)

        filename = f"{node}.mtl"
        filepath = os.path.join(os.path.dirname(config.filepath), filename)
        utils.generate_xml(filepath, doc, overwrite=True, ind=1)
        utils.clear_xml_header(filepath)

        print()
        bcPrint(f"'{filename}' material file has been generated.")


def write_material_information(material_name):
    """Outputs material diagnostic data to the Blender console during processing."""
    parts = material_name.split("__")
    bcPrint(
        f"Subname: '{parts[2]}'  -  Index: '{parts[1]}'  -  Physics Type: '{parts[3]}'"
    )


def get_material_groups(materials):
    """Extracts unique parent material names out of compiled submesh dictionary lists."""
    material_groups = []
    for material_name, material in materials.items():
        group_name = material_name.split("__")[0]
        if group_name not in material_groups:
            material_groups.append(group_name)

    return material_groups


def sort_materials_by_names(unordered_materials):
    """Sorts compiled materials list alphabetically based on structural suffix hashes."""
    materials = OrderedDict()
    for material_name in sorted(unordered_materials):
        materials[material_name] = unordered_materials[material_name]

    return materials


def get_materials(just_selected=False):
    """Extracts all active materials matched across geometries inside export collection bounds."""
    materials = OrderedDict()
    material_counter = {}

    for group in utils.get_mesh_export_nodes(just_selected):
        material_counter[group.name] = 0
        for object_ in group.objects:
            if object_.type != "MESH":
                continue

            for i in range(0, len(object_.material_slots)):
                slot = object_.material_slots[i]
                material = slot.material
                if material is None:
                    continue

                if material not in list(materials.values()):
                    node_name = utils.get_node_name(group)

                    material.name = utils.replace_invalid_rc_characters(material.name)
                    for image in get_textures(material):
                        try:
                            image.name = utils.replace_invalid_rc_characters(image.name)
                        except AttributeError:
                            pass

                    node, index, name, physics = get_material_parts(
                        node_name, slot.material.name
                    )

                    if index == 0:
                        material_counter[group.name] += 1
                        index = material_counter[group.name]

                    material_name = f"{node}__{index:02d}__{name}__{physics}"
                    materials[material_name] = material

    return sort_materials_by_names(materials)


def set_material_attributes(material, material_name, material_node):
    """Maps custom physical material parameters to target XML properties."""
    material_node.setAttribute("Name", get_material_name(material_name))
    material_node.setAttribute("MtlFlags", "524416")

    shader = "Illum"
    if "physProxyNoDraw" == get_material_physic(material_name):
        shader = "Nodraw"

    material_node.setAttribute("Shader", shader)
    material_node.setAttribute("GenMask", "60400000")
    material_node.setAttribute(
        "StringGenMask", "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING"
    )
    material_node.setAttribute("SurfaceType", "")
    material_node.setAttribute("MatTemplate", "")

    use_default = True
    if material.use_nodes and material.node_tree:
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            diffuse = Color(
                (
                    bsdf.inputs["Base Color"].default_value[0],
                    bsdf.inputs["Base Color"].default_value[1],
                    bsdf.inputs["Base Color"].default_value[2],
                )
            )
            specular = 1.0
            opacity = bsdf.inputs["Alpha"].default_value
            shininess = (1.0 - bsdf.inputs["Roughness"].default_value) * 255.0
            use_default = False

    if use_default:
        diffuse = Color(
            (
                material.diffuse_color[0],
                material.diffuse_color[1],
                material.diffuse_color[2],
            )
        )
        specular = 1.0
        opacity = material.diffuse_color[3]
        shininess = (1.0 - material.roughness) * 255.0

    material_node.setAttribute("Diffuse", color_to_xml_string(diffuse))
    material_node.setAttribute("Specular", color_to_xml_string(specular))
    material_node.setAttribute("Opacity", str(opacity))
    material_node.setAttribute("Shininess", str(shininess))
    material_node.setAttribute("vertModifType", "0")
    material_node.setAttribute("LayerAct", "1")


def set_public_params(doc, material, material_node):
    """Creates a basic standard placeholder XML node for custom CryEngine material parameters."""
    public_params = doc.createElement("PublicParams")
    public_params.setAttribute("EmittanceMapGamma", "1")
    public_params.setAttribute("SSSIndex", "0")
    public_params.setAttribute("IndirectColor", "0.25, 0.25, 0.25")
    material_node.appendChild(public_params)


def add_textures(doc, material, material_node, config):
    """Assembles the actual XML texture node hierarchy mapped to the material."""
    textures_node = doc.createElement("Textures")

    diffuse = get_diffuse_texture(material)
    specular = get_specular_texture(material)
    normal = get_normal_texture(material)

    if diffuse:
        texture_node = doc.createElement("Texture")
        texture_node.setAttribute("Map", "Diffuse")
        path = get_image_path_for_game(diffuse, config.game_dir)
        texture_node.setAttribute("File", path)
        textures_node.appendChild(texture_node)
        bcPrint(f"Diffuse Path: {path}.")
    else:
        if "physProxyNoDraw" != get_material_physic(material.name):
            texture_node = doc.createElement("Texture")
            texture_node.setAttribute("Map", "Diffuse")
            path = "%engine%/engineassets/textures/white.dds"
            texture_node.setAttribute("File", path)
            textures_node.appendChild(texture_node)
            bcPrint(f"Diffuse Path: {path}.")

    if specular:
        texture_node = doc.createElement("Texture")
        texture_node.setAttribute("Map", "Specular")
        path = get_image_path_for_game(specular, config.game_dir)
        texture_node.setAttribute("File", path)
        textures_node.appendChild(texture_node)
        bcPrint(f"Specular Path: {path}.")

    if normal:
        texture_node = doc.createElement("Texture")
        texture_node.setAttribute("Map", "Normal")
        path = get_image_path_for_game(normal, config.game_dir)
        texture_node.setAttribute("File", path)
        textures_node.appendChild(texture_node)
        bcPrint(f"Normal Path: {path}.")

    if config.convert_textures:
        convert_image_to_dds([diffuse, specular, normal], config)

    material_node.appendChild(textures_node)


def convert_image_to_dds(images, config):
    """Spawns an RCInstance subprocess to convert images asynchronously to DDS."""
    converter = RCInstance(config)
    converter.convert_tif(images)


def get_textures(material):
    """Gathers all standard mapped texture channels for the material."""
    images = []
    images.append(get_diffuse_texture(material))
    images.append(get_specular_texture(material))
    images.append(get_normal_texture(material))
    return images


def get_diffuse_texture(material):
    """Gathers diffuse/albedo texture channels, gracefully logging potential exception context."""
    image = None
    try:
        if bpy.context.scene.render.engine == "CYCLES":
            if material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == "TEX_IMAGE":
                        if (
                            node.name == "Image Texture"
                            or node.name.lower().find("diffuse") != -1
                        ):
                            image = node.image
                            if is_valid_image(image):
                                return image
        else:
            for slot in material.texture_slots:
                if slot and slot.texture.type == "IMAGE":
                    if slot.use_map_color_diffuse:
                        image = slot.texture.image
                        if is_valid_image(image):
                            return image
    except Exception as e:
        # Extract name cleanly or fallback to string representation safely
        mat_name = getattr(material, "name", str(material))
        bcPrint(f"Failed to fetch diffuse texture for '{mat_name}': {e}", "warning")

    return None


def get_specular_texture(material):
    """Gathers specular texture channels, gracefully logging potential exception context."""
    image = None
    try:
        if bpy.context.scene.render.engine == "CYCLES":
            if material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == "TEX_IMAGE":
                        if node.name.lower().find("specular") != -1:
                            image = node.image
                            if is_valid_image(image):
                                return image
        else:
            for slot in material.texture_slots:
                if slot and slot.texture.type == "IMAGE":
                    if slot.use_map_color_spec or slot.use_map_specular:
                        image = slot.texture.image
                        if is_valid_image(image):
                            return image
    except Exception as e:
        # Extract name cleanly or fallback to string representation safely
        mat_name = getattr(material, "name", str(material))
        bcPrint(f"Failed to fetch specular texture for '{mat_name}': {e}", "warning")

    return None


def get_normal_texture(material):
    """Gathers normal/bump texture channels, gracefully logging potential exception context."""
    image = None
    try:
        if bpy.context.scene.render.engine == "CYCLES":
            if material.node_tree:
                for node in material.node_tree.nodes:
                    if node.type == "TEX_IMAGE":
                        if node.name.lower().find("normal") != -1:
                            image = node.image
                            if is_valid_image(image):
                                return image
        else:
            for slot in material.texture_slots:
                if slot and slot.texture.type == "IMAGE":
                    if slot.use_map_color_normal:
                        image = slot.texture.image
                        if is_valid_image(image):
                            return image
    except Exception as e:
        # Extract name cleanly or fallback to string representation safely
        mat_name = getattr(material, "name", str(material))
        bcPrint(f"Failed to fetch normal texture for '{mat_name}': {e}", "warning")

    return None


def color_to_string(color, a):
    """Formates color and alpha parameters to an XML text representation."""
    if isinstance(color, (float, int)):
        return f"{color:f} {color:f} {color:f} {a:f}"
    elif type(color).__name__ == "Color":
        return f"{color.r:f} {color.g:f} {color.b:f} {a:f}"


def color_to_xml_string(color):
    """Formates standard Color vector maps to XML parameter attributes."""
    if isinstance(color, (float, int)):
        return f"{color:f},{color:f},{color:f}"
    elif type(color).__name__ == "Color":
        return f"{color[0]:f},{color[1]:f},{color[2]:f}"


def get_material_counter():
    """Generates standard material dictionaries parsed against CryExportNode collections."""
    material_counter = {}
    for collection in bpy.data.collections:
        if utils.is_export_node(collection):
            material_counter[collection.name] = 0
    return material_counter


def get_material_physics():
    """Builds a map linking active material names to custom physical tags."""
    physics_properties = {}
    for material in bpy.data.materials:
        properties = extract_bcry_properties(material.name)
        if properties and properties.get("Physics"):
            physics_properties[properties["Name"]] = properties.get("Physics")
    return physics_properties


def get_materials_per_group(collection):
    """Gathers all assigned materials matched within a registered collection."""
    materials = []
    if collection in bpy.data.collections:
        for obj in bpy.data.collections[collection].objects:
            if obj.type == "MESH":
                for material in obj.data.materials:
                    if material is not None and material.name not in materials:
                        materials.append(material.name)
    return materials


def get_material_color(material, type_):
    """Formats custom diffuse/emission channels to standard COLLADA floats."""
    color = 0.0
    alpha = 1.0

    if type_ == "emission":
        color = 0.0
    elif type_ == "ambient":
        color = 0.0
    elif type_ == "diffuse":
        col = material.diffuse_color
        color = Color((col[0], col[1], col[2]))
        alpha = col[3]
    elif type_ == "specular":
        color = 1.0

    return color_to_string(color, alpha)


def get_material_attribute(material, type_):
    """Converts viewport float limits to standard XML text properties."""
    val = 0.0
    if type_ == "shininess":
        val = (1.0 - material.roughness) * 255.0
    elif type_ == "index_refraction":
        val = material.diffuse_color[3]

    return str(val)


def get_material_parts(node, material):
    """Decodes standard naming segments to extract hierarchy indices and custom physics tags."""
    VALID_PHYSICS = (
        "physDefault",
        "physProxyNoDraw",
        "physNoCollide",
        "physObstruct",
        "physNone",
    )

    parts = material.split("__")
    count = len(parts)

    group = node
    index = 0
    name = material
    physics = "physNone"

    if count == 1:
        index = 0
    elif count == 2:
        if parts[1] not in VALID_PHYSICS:
            try:
                index = int(parts[0])
                name = parts[1]
            except ValueError:
                index = 0
                name = material
        else:
            name = parts[0]
            physics = parts[1]
    elif count == 3:
        try:
            index = int(parts[0])
            name = parts[1]
            physics = parts[2]
        except ValueError:
            index = 0
            name = material
    elif count >= 4:
        group = parts[0]
        try:
            index = int(parts[1])
            name = parts[2]
            physics = parts[3]
        except ValueError:
            index = 0
            name = material

    name = utils.replace_invalid_rc_characters(name)
    if physics not in VALID_PHYSICS:
        physics = "physNone"

    return group, index, name, physics


def extract_bcry_properties(material_name):
    """Regex parser to extract property indices from naming strings."""
    if is_bcry_material(material_name):
        groups = re.findall("(.+)__([0-9]+)__(.*)__(phys[A-Za-z0-9]+)", material_name)
        properties = {}
        properties["ExportNode"] = groups[0][0]
        properties["Number"] = int(groups[0][1])
        properties["Name"] = groups[0][2]
        properties["Physics"] = groups[0][3]
        return properties
    else:
        is_with_numbers = is_bcry_material_with_numbers(material_name)
        is_with_phys = is_bcry_material_with_phys(material_name)
        properties = {}
        if is_with_numbers:
            groups = re.findall("([0-9]+)__(.*)", material_name)
            properties["Number"] = int(groups[0][0])
            properties["Name"] = groups[0][1]
        if is_with_phys:
            groups = re.findall("(.*)__(phys[A-Za-z0-9]+)", material_name)
            properties["Name"] = groups[0][0]
            properties["Physics"] = groups[0][1]
        if is_with_numbers or is_with_phys:
            return properties
    return None


def remove_bcry_properties(material_name):
    """Removes all BCRY exporter metadata segments to return the clean naming string."""
    properties = extract_bcry_properties(material_name)
    if properties:
        return str(properties["Name"])
    return material_name


def is_bcry_material(material_name):
    """Checks if naming layout contains export groups, indices, and active physics suffixes."""
    return bool(re.search(".+__[0-9]+__.*__phys[A-Za-z0-9]+", material_name))


def is_bcry_material_with_numbers(material_name):
    """Checks if naming layout prefix contains numeric index parameters."""
    return bool(re.search("[0-9]+__.*", material_name))


def is_bcry_material_with_phys(material_name):
    """Checks if naming layout suffix contains active physical proxy identifiers."""
    return bool(re.search(".*__phys[A-Za-z0-9]+", material_name))


def get_material_name(material_name):
    """Grabs raw material subname from standard format."""
    try:
        return material_name.split("__")[2]
    except Exception:
        raise exceptions.BCryException(
            "Material naming layout does not match standard BCRY parameters!"
        )


def get_material_physic(material_name):
    """Grabs active physical material configuration mapped to naming conventions."""
    index = material_name.find("__phys")
    if index != -1:
        return material_name[index + 2 :]

    return "physNone"


def set_material_physic(self, context, phys_name):
    """Action callback to update active material physics properties directly in naming strings."""
    if not phys_name.startswith("__"):
        phys_name = f"__{phys_name}"

    me = context.active_object
    if me and me.active_material:
        me.active_material.name = replace_phys_material(
            me.active_material.name, phys_name
        )

    return {"FINISHED"}


def replace_phys_material(material_name, phys):
    """Swaps material physical tags."""
    if "__phys" in material_name:
        return re.sub(r"__phys.*", phys, material_name)
    else:
        return f"{material_name}{phys}"


def is_valid_image(image):
    """Checks if a Blender Image object contains loaded pixels and file system paths."""
    try:
        return image and image.has_data and image.filepath
    except Exception:
        return False


def get_image_path_for_game(image, game_dir):
    """Constructs absolute paths to DDS textures, mapping them relatively inside game root directory."""
    if not game_dir or not os.path.isdir(game_dir):
        raise exceptions.NoGameDirectorySelected()

    image_path = os.path.normpath(bpy.path.abspath(image.filepath))
    image_path = f"{os.path.splitext(image_path)[0]}.dds"
    image_path = os.path.relpath(image_path, game_dir)
    return image_path
