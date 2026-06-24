# ------------------------------------------------------------------------------
# Name:        utils/export_node.py
# Purpose:     Export node resolution, COLLADA XML generators, and scene filters
# ------------------------------------------------------------------------------

import os
import random
import re
import bpy
from xml.dom.minidom import Document, parseString

# Import custom core modules and sibling utils
from ..core import exceptions
from ..core.logger import bcPrint
from .math import floats_to_string, strings_to_string


def select_all():
    """Selects all objects in the current Blender scene."""
    for object_ in bpy.data.objects:
        object_.select_set(True)


def deselect_all():
    """Deselects all objects in the current Blender scene."""
    for object_ in bpy.data.objects:
        object_.select_set(False)


def set_active(object_):
    """Sets the active object in the viewport context."""
    bpy.context.view_layer.objects.active = object_


def get_xsi_filetype_value(node):
    """Maps the export node extension/type to an XSI custom property integer representation."""
    node_type = get_node_type(node)
    if node_type == "cgf":
        return "1"
    elif node_type == "chr":
        return "4"
    elif node_type == "cga":
        return "18"
    elif node_type == "skin":
        return "32"
    elif node_type in ("i_caf", "anm"):
        return "64"
    else:
        return "1"


def get_geometry_name(group, object_):
    """Generates the standardized, unique COLLADA geometry ID for a given mesh object."""
    node_name = get_node_name(group)
    if is_bone_geometry(object_):
        return f"{node_name}_{object_.name}"
    elif is_lod_geometry(object_):
        return f"{node_name}_{changed_lod_name(object_.name)}"
    else:
        return f"{node_name}_{object_.name}_geometry"


def clean_file(just_selected=False):
    """Pre-processes active object names to sanitize characters for the CryEngine Resource Compiler."""
    for node in get_export_nodes(just_selected):
        node_name = get_node_name(node)
        nodetype = get_node_type(node)
        node_name = replace_invalid_rc_characters(node_name)
        node.name = f"{node_name}.{nodetype}"

        for object_ in node.objects:
            object_.name = replace_invalid_rc_characters(object_.name)
            try:
                object_.data.name = replace_invalid_rc_characters(object_.data.name)
            except AttributeError:
                pass

            if object_.type == "ARMATURE":
                for bone in object_.data.bones:
                    bone.name = replace_invalid_rc_characters(bone.name)


def replace_invalid_rc_characters(string):
    """Sanitizes names of meshes, bones, and textures to prevent Resource Compiler parser errors."""
    string = string.strip()
    string = "__".join(string.split())

    character_map = {
        "a": "àáâå",
        "c": "ç",
        "e": "èéêë",
        "i": "ìíîïı",
        "l": "ł",
        "n": "ñ",
        "o": "òóô",
        "u": "ùúû",
        "y": "ÿ",
        "ss": "ß",
        "ae": "äæ",
        "oe": "ö",
        "ue": "ü",
    }

    # Perform character replacements
    for good, bad in character_map.items():
        for char in bad:
            string = string.replace(char, good)
            string = string.replace(char.upper(), good.upper())

    # Eliminate non-alphanumeric values (except periods, underscores, and dollar signs)
    string = re.sub("[^.^_^$0-9A-Za-z]", "", string)
    return string


def fix_weights():
    """Forces normalizations across all vertex weights to prevent CryEngine rigging errors."""
    for object_ in get_type("skins"):
        override_ctx = override(object_)
        try:
            with bpy.context.temp_override(**override_ctx):
                bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        except Exception as e:
            raise exceptions.BCryException(
                f"Failed to normalize weights. Please fix weightless vertices: {e}"
            )

    bcPrint("Rig weights normalized.")


# ------------------------------------------------------------------------------
# Export Nodes Parsing
# ------------------------------------------------------------------------------


def get_export_nodes(just_selected=False):
    """Retrieves all registered CryExportNode collections containing active meshes."""
    export_nodes = []

    if just_selected:
        return __get_selected_nodes()

    export_nodes_collection = bpy.data.collections.get("cry_export_nodes")
    if export_nodes_collection is not None:
        for collection in bpy.data.collections:
            if is_export_node(collection) and len(collection.objects) > 0:
                export_nodes.append(collection)

    bcPrint(f"Export nodes parsed: {len(export_nodes)}")
    return export_nodes


def get_mesh_export_nodes(just_selected=False):
    """Filters CryExportNode collections to return only geometry-related structures."""
    export_nodes = []
    ALLOWED_NODE_TYPES = ("cgf", "cga", "chr", "skin")
    for node in get_export_nodes(just_selected):
        if get_node_type(node) in ALLOWED_NODE_TYPES:
            export_nodes.append(node)

    return export_nodes


def get_chr_node_from_skeleton(armature):
    """Identifies the skeletal .chr export group linked to the active armature."""
    for child in armature.children:
        for collection in child.users_collection:
            if collection.name.endswith(".chr"):
                return collection
    return None


def get_chr_object_from_skeleton(armature):
    """Locates the skin/mesh associated with the parent bone of a skeletal node."""
    for child in armature.children:
        for group in child.users_collection:
            if group.name.endswith(".chr"):
                return child
    return None


def get_chr_names(just_selected=False):
    """Returns a list of all active skeletal CHR node names."""
    chr_names = []
    for node in get_export_nodes(just_selected):
        if get_node_type(node) == "chr":
            chr_names.append(get_node_name(node))

    return chr_names


def get_animation_export_nodes(just_selected=False):
    """Extracts animation-specific export node targets (.anm, .i_caf)."""
    export_nodes = []

    if just_selected:
        return __get_selected_nodes()

    export_nodes_collection = bpy.data.collections.get("cry_export_nodes")
    if export_nodes_collection is not None:
        ALLOWED_NODE_TYPES = ("anm", "i_caf")
        for collection in bpy.data.collections:
            if is_export_node(collection) and len(collection.objects) > 0:
                if get_node_type(collection) in ALLOWED_NODE_TYPES:
                    export_nodes.append(collection)

    return export_nodes


def __get_selected_nodes():
    """Identifies active export node collections based on active selection states."""
    export_nodes = []
    for obj in bpy.context.selected_objects:
        for group in obj.users_collection:
            if is_export_node(group) and group not in export_nodes:
                export_nodes.append(group)

    return export_nodes


def get_type(type_):
    """Dispatcher to isolate structural object categories during active export passes."""
    dispatch = {
        "objects": __get_objects,
        "geometry": __get_geometry,
        "controllers": __get_controllers,
        "skins": __get_skins,
        "fakebones": __get_fakebones,
        "bone_geometry": __get_bone_geometry,
    }
    return list(set(dispatch[type_]()))


def _get_armature_for_object(object_):
    """Internal helper to identify connected armature via parent or modifier."""
    if object_.parent is not None and object_.parent.type == "ARMATURE":
        return object_.parent
    for mod in object_.modifiers:
        if mod.type == "ARMATURE" and mod.object:
            return mod.object
    return None


def __get_objects():
    items = []
    for group in get_export_nodes():
        items.extend(group.objects)
    return items


def __get_geometry():
    items = []
    for object_ in get_type("objects"):
        if object_.type == "MESH" and not object_.get("fakebone"):
            items.append(object_)
    return items


def __get_controllers():
    items = []
    for object_ in get_type("objects"):
        if not (is_bone_geometry(object_) or object_.get("fakebone")):
            arm = _get_armature_for_object(object_)
            if arm:
                items.append(arm)
    return items


def __get_skins():
    items = []
    for object_ in get_type("objects"):
        if object_.type == "MESH":
            if not (is_bone_geometry(object_) or object_.get("fakebone")):
                arm = _get_armature_for_object(object_)
                if arm:
                    items.append(object_)
    return items


def __get_fakebones():
    return [obj for obj in bpy.data.objects if obj.get("fakebone")]


def __get_bone_geometry():
    items = []
    for object_ in get_type("objects"):
        if is_bone_geometry(object_):
            items.append(object_)
    return items


def is_export_node(node):
    """Identifies if a collection is a valid BCRY CryExportNode."""
    extensions = [".cgf", ".cga", ".chr", ".skin", ".anm", ".i_caf"]
    for extension in extensions:
        if node.name.endswith(extension):
            if node.name in bpy.data.collections["cry_export_nodes"].children:
                return True
    return False


def are_duplicate_nodes():
    """Asserts if there are multiple active export nodes sharing identical names."""
    node_names = []
    for group in get_export_nodes():
        node_names.append(get_node_name(group))
    unique_node_names = set(node_names)
    return len(unique_node_names) < len(node_names)


def get_node_name(node):
    """Strips file extensions to return the actual clean export node name."""
    node_type = get_node_type(node)
    return node.name[: -(len(node_type) + 1)]


def get_node_type(node):
    """Returns the type/extension of a registered export node."""
    node_components = node.name.split(".")
    return node_components[-1]


def is_visual_scene_node_writed(object_, group):
    """Asserts if the given mesh target qualifies as a COLLADA Scene Node entry."""
    if is_bone_geometry(object_):
        return False
    if object_.parent is not None and object_.type not in ("MESH", "EMPTY"):
        return False
    return True


def is_there_a_parent_releation(object_, group):
    """Asserts the presence of parent hierarchies within the scope of the export group."""
    while object_.parent:
        if is_object_in_group(object_.parent, group) and object_.parent.type in (
            "MESH",
            "EMPTY",
        ):
            return True
        else:
            return is_there_a_parent_releation(object_.parent, group)
    return False


def is_object_in_group(object_, group):
    """Verifies if the given object is linked to the specified group collection."""
    for obj in group.objects:
        if object_.name == obj.name:
            return True
    return False


def is_dummy(object_):
    """Identifies if the Blender object acts as a dummy/null helper (Empty node)."""
    return object_.type == "EMPTY"


# ------------------------------------------------------------------------------
# Animation Specific Node Parsers
# ------------------------------------------------------------------------------


def get_animation_id(group):
    """Generates the unique string key matching the CGA/CHR animation track hierarchy."""
    node_name = get_node_name(group)
    return f"{node_name}-{node_name}"


def get_geometry_animation_file_name(collection):
    """Resolves correct CGA geometry animation tracks (.anm)."""
    node_name = get_node_name(collection)
    cga_node = find_cga_node_from_anm_node(collection)
    cga_name = get_node_name(cga_node) if cga_node else collection.objects[0].name
    return f"{cga_name}_{node_name}.anm"


def get_cryasset_animation_file_name(collection):
    """Resolves CryEngine's secondary .cryasset tracker files matching .anm tracks."""
    node_name = get_node_name(collection)
    cga_node = find_cga_node_from_anm_node(collection)
    cga_name = get_node_name(cga_node) if cga_node else collection.objects[0].name
    return f"{cga_name}_{node_name}.anm.cryasset"


def find_cga_node_from_anm_node(anm_group):
    """Finds CGA node assignments associated with custom animation tracks."""
    for object_ in anm_group.objects:
        for group in object_.users_collection:
            if get_node_type(group) == "cga":
                return group
    return None


# ------------------------------------------------------------------------------
# Levels of Detail (LODs)
# ------------------------------------------------------------------------------


def is_lod_geometry(object_):
    """Verifies if the object represents a secondary Level of Detail mesh step."""
    if object_.name[:-1].endswith("_LOD"):
        # Rigged characters and skins are processed holistically, ignoring LOD suffixes
        for group in object_.users_collection:
            if get_node_type(group) in ("chr", "skin"):
                return False
        return True
    return False


def is_has_lod(object_):
    """Asserts if the target mesh has active LOD structures associated with it."""
    for group in object_.users_collection:
        if get_node_type(group) in ("chr", "skin"):
            return False
    lod_base_name = f"{object_.name}_LOD"
    for obj in bpy.data.objects:
        if obj.name.startswith(lod_base_name):
            return True
    return False


def changed_lod_name(lod_name):
    """Transforms standard Blender LOD suffixes to resolve matching COLLADA namespaces."""
    index = lod_name[-1]
    return f"_lod{index}_{lod_name[:-5]}"


def get_lod_geometries(object_):
    """Retrieves all Blender meshes mapped as Levels of Detail steps for the parent object."""
    lods = []
    lod_base_name = f"{object_.name}_LOD"
    for obj in bpy.data.objects:
        if obj.name.startswith(lod_base_name):
            lods.append(obj)
    return lods


# ------------------------------------------------------------------------------
# Physics / Skeletal Helpers
# ------------------------------------------------------------------------------


def get_bone_geometry(bone):
    """Extracts mesh references mapped as physical proxies for structural skeleton rigging."""
    bone_name = bone.name
    if bone_name.endswith("_Phys"):
        bone_name = bone_name[:-5]
    return bpy.data.objects.get(f"{bone_name}_boneGeometry", None)


def is_bone_geometry(object_):
    """Verifies if the mesh is a bone proxy physics helper."""
    return object_.type == "MESH" and object_.name.endswith("_boneGeometry")


def is_physic_bone(bone):
    """Identifies physical rig components."""
    return bone.name.endswith("_Phys")


def make_physic_bone(bone):
    """Renames standard bone channels to register cleanly as physical colliders."""
    if bone.name.endswith(".001"):
        bone.name = bone.name.replace(".001", "_Phys")
    else:
        bone.name = f"{bone.name}_Phys"


def get_armature_physic(armature):
    """Returns the physical skeleton proxy associated with the active armature."""
    physic_name = f"{armature.name}_Phys"
    return bpy.data.objects.get(physic_name, None)


def get_bone_material_type(bone, bone_type):
    """Maps custom physical materials depending on anatomical limb locations."""
    if bone_type in ("leg", "arm", "foot"):
        left_list = ["left", ".l"]
        prefix = "l" if is_in_list(bone.name, left_list) else "r"
        return f"{prefix}{bone_type}"
    elif bone_type == "other":
        return "primitive"
    return bone_type


def get_bone_type(bone):
    """Anatomical bone parser for auto-ragdoll materials mapping."""
    if is_leg_bone(bone):
        return "leg"
    elif is_arm_bone(bone):
        return "arm"
    elif is_torso_bone(bone):
        return "torso"
    elif is_head_bone(bone):
        return "head"
    elif is_foot_bone(bone):
        return "foot"
    else:
        return "other"


def is_leg_bone(bone):
    return is_in_list(bone.name, ["leg", "thigh", "calf"])


def is_arm_bone(bone):
    return is_in_list(bone.name, ["arm", "hand"])


def is_torso_bone(bone):
    return is_in_list(bone.name, ["hips", "pelvis", "spine", "chest", "torso"])


def is_head_bone(bone):
    return is_in_list(bone.name, ["head", "neck"])


def is_foot_bone(bone):
    return is_in_list(bone.name, ["foot", "toe"])


def is_in_list(str_val, list_):
    """Utility to perform case-insensitive substring searches across keylists."""
    for sub in list_:
        if str_val.lower().find(sub) != -1:
            return True
    return False


def get_animation_node_range(object_, node_name, initial_start, initial_end):
    """Extracts frame limit parameters from custom properties with timeline marker fallback."""
    try:
        start_frame = object_[f"{node_name}_Start"]
        end_frame = object_[f"{node_name}_End"]

        if isinstance(start_frame, str) and isinstance(end_frame, str):
            tm = bpy.context.scene.timeline_markers
            if tm.find(start_frame) != -1 and tm.find(end_frame) != -1:
                return tm[start_frame].frame, tm[end_frame].frame
            else:
                raise exceptions.MarkersNotFound()
        else:
            return start_frame, end_frame
    except Exception as e:
        bcPrint(
            f"Range lookup failed for '{node_name}': {e}. Using timeline default.",
            "warning",
        )
        return initial_start, initial_end


def get_object_children(parent):
    """Retrieves all direct viewport children objects."""
    return [
        child
        for child in parent.children
        if child.type in {"ARMATURE", "EMPTY", "MESH"}
    ]


def parent(children, parent_obj):
    """Pairs viewport children meshes to a parent controller node."""
    for object_ in children:
        object_.parent = parent_obj


# ------------------------------------------------------------------------------
# Context Overrides
# ------------------------------------------------------------------------------


def get_3d_context(object_):
    """Builds manual UI screen overrides to force-execute operators requiring View3D regions."""
    window = bpy.context.window
    screen = window.screen
    area3d = None
    region3d = None

    for area in screen.areas:
        if area.type == "VIEW_3D":
            area3d = area
            break

    if area3d:
        for region in area3d.regions:
            if region.type == "WINDOW":
                region3d = region
                break

    override_dict = {
        "window": window,
        "screen": screen,
        "area": area3d,
        "region": region3d,
        "object": object_,
    }
    return override_dict


def override(obj, active=True, selected=True):
    """Constructs complex execution dictionary overrides for modern evaluated depsgraphs."""
    ctx = bpy.context.copy()
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            ctx["area"] = area
            ctx["region"] = area.regions[-1]
            break

    if active:
        ctx["active_object"] = obj
        ctx["active_base"] = obj
        ctx["object"] = obj

    if selected:
        ctx["selected_objects"] = [obj]
        ctx["selected_bases"] = [obj]
        ctx["selected_editable_objects"] = [obj]
        ctx["selected_editable_bases"] = [obj]

    return ctx


# ------------------------------------------------------------------------------
# Layer / UUID Generator
# ------------------------------------------------------------------------------


def get_guid():
    """Generates standard Microsoft-compliant GUIDs used for editor scene assembly."""
    return f"{{{_random_hex_sector(8)}-{_random_hex_sector(4)}-{_random_hex_sector(4)}-{_random_hex_sector(4)}-{_random_hex_sector(12)}}}"


def _random_hex_sector(length):
    fixed_length_hex_format = f"%0{length}x"
    return fixed_length_hex_format % random.randrange(16**length)


# ------------------------------------------------------------------------------
# Raw COLLADA Writers & File Generators
# ------------------------------------------------------------------------------


def generate_file_contents(type_):
    """Returns baseline XML layouts for CryEngine CDF/CHRPARAMS definitions."""
    if type_ == "chrparams":
        return (
            "<Params>\n"
            "<AnimationList>\n"
            '<Animation name="???" path="???.caf"/>\n'
            "</AnimationList>\n"
            "</Params>"
        )
    elif type_ == "cdf":
        return (
            "<CharacterDefinition>\n"
            '<Model File="???.chr" Material="???"/>\n'
            "<AttachmentList>\n"
            '<Attachment Type="CA_BONE" AName="???" Rotation="1,0,0,0" Position="0,0,0" BoneName="???" Flags="0"/>\n'
            '<Attachment Type="CA_SKIN" AName="???" Binding="???.skin" Flags="0"/>\n'
            "</AttachmentList>\n"
            '<ShapeDeformation COL0="0" COL1="0" COL2="0" COL3="0" COL4="0" COL5="0" COL6="0" COL7="0"/>\n'
            "</CharacterDefinition>"
        )


def generate_file(filepath, contents, overwrite=False):
    """Low-level file generation writer."""
    if not os.path.exists(filepath) or overwrite:
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(contents)


def generate_xml(filepath, contents, overwrite=False, ind=4):
    """Resolves standard structured XML formatting via Python minidom DOM nodes."""
    if not os.path.exists(filepath) or overwrite:
        if isinstance(contents, str):
            script = parseString(contents)
        else:
            script = contents
        formatted_contents = script.toprettyxml(indent=" " * ind)
        generate_file(filepath, formatted_contents, overwrite)


def clear_xml_header(filepath):
    """Strips Python xml.dom.minidom default XML headers.

    This matches standard layouts expected by the Resource Compiler.
    """
    with open(filepath, "r", encoding="utf-8") as file:
        lines = file.readlines()

    if not lines or lines[0].find("<?xml version") == -1:
        return filepath

    lines = lines[1:]
    with open(filepath, "w", encoding="utf-8") as file:
        for line in lines:
            file.write(line)


def remove_file(filepath):
    """Deletes a file safely on disk."""
    if os.path.exists(filepath):
        os.remove(filepath)


def write_source(id_, type_, array, params):
    """Assembles a COLLADA XML <source> structure element containing geometry values."""
    doc = Document()
    length = len(array)
    if type_ == "float4x4":
        stride = 16
    elif len(params) == 0:
        stride = 1
    else:
        stride = len(params)
    count = int(length / stride)

    source = doc.createElement("source")
    source.setAttribute("id", id_)

    if type_ == "float4x4":
        source_data = doc.createElement("float_array")
    else:
        source_data = doc.createElement(f"{type_}_array")
    source_data.setAttribute("id", f"{id_}-array")
    source_data.setAttribute("count", str(length))

    try:
        source_data.appendChild(doc.createTextNode(floats_to_string(array)))
    except TypeError:
        source_data.appendChild(doc.createTextNode(strings_to_string(array)))

    technique_common = doc.createElement("technique_common")
    accessor = doc.createElement("accessor")
    accessor.setAttribute("source", f"#{id_}-array")
    accessor.setAttribute("count", str(count))
    accessor.setAttribute("stride", str(stride))

    for param in params:
        param_node = doc.createElement("param")
        param_node.setAttribute("name", param)
        param_node.setAttribute("type", type_)
        accessor.appendChild(param_node)

    if len(params) == 0:
        param_node = doc.createElement("param")
        param_node.setAttribute("type", type_)
        accessor.appendChild(param_node)

    technique_common.appendChild(accessor)
    source.appendChild(source_data)
    source.appendChild(technique_common)

    return source


def write_input(name, offset, type_, semantic):
    """Assembles a COLLADA XML <input> element linking geometric variables."""
    doc = Document()
    id_ = f"{name}-{type_}"
    input_node = doc.createElement("input")

    if offset is not None:
        input_node.setAttribute("offset", str(offset))
    input_node.setAttribute("semantic", semantic)
    input_node.setAttribute("source", f"#{id_}")

    return input_node
