# ------------------------------------------------------------------------------
# Name:        utils/armature.py
# Purpose:     Armature transformations, fakebones, animation baking, and bone helpers
# ------------------------------------------------------------------------------

import bpy

from ..core.logger import bcPrint
from .math import transform_bone_matrix, transform_animation_matrix
from .mesh import remove_unused_meshes, remove_unused_actions


def set_active(object_):
    """Helper to set an object as active in the current viewport context."""
    bpy.context.view_layer.objects.active = object_


def deselect_all():
    """Helper to deselect all objects in the scene."""
    for obj in bpy.data.objects:
        obj.select_set(False)


def get_joint_name(object_, index=1):
    """Generates a unique joint helper name ($joint01, $joint02, etc.) for the object's children."""
    joint_name = f"$joint{index:02d}"

    for child in object_.children:
        if child.name == joint_name:
            return get_joint_name(object_, index + 1)

    return joint_name


def rebuild_armature(armature):
    """Rebuilds the active armature's edit bones from scratch.

    Fixes potential export offset errors or structural corruption by transferring heads,
    tails, rolls, parents, custom properties, and action animation data.
    """
    old_bones = []
    new_bones = []
    obj_childrens = []
    temp_suffix = "+oldbcry"

    # Collect list of children in armature to fix vertex group references later
    for obj in armature.children:
        obj_childrens.append(obj)

    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = armature.data.edit_bones
    bones_count = len(edit_bones)

    # Collect old bones list
    for bone in edit_bones:
        old_bones.append(bone)

    # Create new bone slots
    for i in range(bones_count):
        new_bone = edit_bones.new(str(i))
        new_bones.append(new_bone)

    for i in range(bones_count):
        # Copy basic parameters
        new_bones[i].head = old_bones[i].head
        new_bones[i].tail = old_bones[i].tail
        new_bones[i].roll = old_bones[i].roll
        new_bones[i].use_connect = old_bones[i].use_connect
        new_bones[i].use_deform = old_bones[i].use_deform
        old_name = old_bones[i].name
        old_bones[i].name = old_bones[i].name + temp_suffix
        new_bones[i].name = old_name

        # Copy custom properties
        if len(old_bones[i].items()) > 0:
            for p in old_bones[i].items():
                new_bones[i][p[0]] = p[1]

    # Re-link parents
    for bone in edit_bones:
        if bone.name.endswith(temp_suffix):
            if bone.parent is not None:
                split_name = bone.name.split("+")
                temp_name = split_name[0]
                split_name = bone.parent.name.split("+")
                parent_name = split_name[0]
                edit_bones[temp_name].parent = edit_bones[parent_name]

    # Remove temporary old bones
    for i in range(bones_count):
        edit_bones.remove(old_bones[i])

    bpy.ops.object.mode_set(mode="OBJECT")

    # Fix vertex groups on child meshes
    if len(obj_childrens) > 0:
        for obj in armature.children:
            if obj.type == "MESH":
                for v in obj.vertex_groups.values():
                    if v.name.endswith(temp_suffix):
                        split_name = v.name.split("+")
                        v.name = split_name[0]

    # Rename action tracks assigned via NLA strips
    if len(bpy.data.actions) > 0:
        for action in bpy.data.actions:
            for fc in action.fcurves:
                if fc.data_path:
                    if temp_suffix in fc.data_path:
                        fc.data_path = fc.data_path.replace(temp_suffix, "")

                if fc.group:
                    if temp_suffix in fc.group.name:
                        fc.group.name = fc.group.name.replace(temp_suffix, "")


def get_fakebone(bone_name):
    """Retrieves the fakebone (transform helper cube) associated with a bone name."""
    for obj in bpy.data.objects:
        if is_fakebone(obj) and obj.name == bone_name:
            return obj
    return None


def is_fakebone(object_):
    """Identifies if a Blender object is a registered fakebone export helper."""
    return object_.get("fakebone") is not None


def add_fakebones(group=None):
    """Constructs proxy cubic meshes (fakebones) to bake and track skeletal bone transforms."""
    scene = bpy.context.scene

    # Ensure the active layer collection is visible to prevent instantiation failures
    x = bpy.context.view_layer.layer_collection
    bpy.context.view_layer.active_layer_collection = x
    remove_unused_meshes()

    armature = None
    if group:
        for object_ in group.objects:
            if object_.type == "ARMATURE":
                armature = object_
    else:
        armature = get_armature()

    if armature is None:
        return

    skeleton = armature.data
    skeleton.pose_position = "REST"
    bpy.context.view_layer.update()

    scene.frame_set(scene.frame_start)
    for pose_bone in armature.pose.bones:
        bone_matrix = transform_bone_matrix(pose_bone)

        bpy.ops.mesh.primitive_cube_add(size=0.01)
        fakebone = bpy.context.active_object
        fakebone.matrix_world = bone_matrix
        fakebone.scale = (1, 1, 1)
        fakebone.name = pose_bone.name
        fakebone["fakebone"] = "fakebone"

        # Parent the proxy helper to the bone
        fakebone.parent = armature
        fakebone.parent_type = "BONE"
        fakebone.parent_bone = pose_bone.name

        fakebone.users_collection[0].objects.unlink(fakebone)

        if group:
            group.objects.link(fakebone)
        else:
            armature.users_collection[0].objects.link(fakebone)

    if group and group.name.split(".")[-1] == "i_caf":
        process_animation(armature, skeleton)


def remove_fakebones():
    """Deletes all helper fakebone meshes from the active scene."""
    fakebones = [obj for obj in bpy.data.objects if is_fakebone(obj)]
    if not fakebones:
        return

    old_mode = bpy.context.mode
    if old_mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    deselect_all()
    for fakebone in fakebones:
        fakebone.select_set(True)

    bpy.ops.object.delete(use_global=False)

    if old_mode != "OBJECT":
        bpy.ops.object.mode_set(mode=old_mode)


def process_animation(armature, skeleton):
    """Processes skeletal pose parameters and triggers keyframe generation."""
    skeleton.pose_position = "POSE"
    bpy.context.view_layer.update()

    location_list, rotation_list = get_keyframes(armature)
    set_keyframes(armature, location_list, rotation_list)


def get_keyframes(armature):
    """Extracts raw decompiled bone coordinates (translation and rotation) frame-by-frame."""
    location_list = []
    rotation_list = []

    for frame in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 1):
        bpy.context.scene.frame_set(frame)

        locations = {}
        rotations = {}

        for bone in armature.pose.bones:
            bone_matrix = transform_animation_matrix(bone.matrix)

            # Parent adjustment checks
            if bone.parent:
                parent_matrix = transform_animation_matrix(bone.parent.matrix)
                bone_matrix = parent_matrix.inverted() @ bone_matrix

            locations[bone.name] = bone_matrix.to_translation()
            rotations[bone.name] = bone_matrix.to_euler()

        location_list.append(locations)
        rotation_list.append(rotations)

    bcPrint("Keyframes parsed successfully.")
    return location_list, rotation_list


def set_keyframes(armature, location_list, rotation_list):
    """Applies coordinates from the parsed keyframe list back to the skeletal controllers."""
    bpy.context.scene.frame_set(bpy.context.scene.frame_start)

    for frame in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 1):
        set_keyframe(armature, frame, location_list, rotation_list)

    bpy.context.scene.frame_set(bpy.context.scene.frame_start)
    bcPrint("Baked keyframe data back to armature helpers.")


def set_keyframe(armature, frame, location_list, rotation_list):
    """Applies translation and rotation matrices on a single frame step."""
    bpy.context.scene.frame_set(frame)
    idx = frame - bpy.context.scene.frame_start
    locations = location_list[idx]
    rotations = rotation_list[idx]

    for bone_name, loc in locations.items():
        fakebone = get_fakebone(bone_name)
        if fakebone:
            fakebone.location = loc
            fakebone.rotation_euler = rotations[bone_name]
            fakebone.keyframe_insert("location", index=-1, frame=frame)
            fakebone.keyframe_insert("rotation_euler", index=-1, frame=frame)


def apply_animation_scale(armature):
    """Bakes skeletal scaling operations across a NLA track pipeline."""
    scene = bpy.context.scene
    x = bpy.context.view_layer.layer_collection
    bpy.context.view_layer.active_layer_collection = x
    remove_unused_meshes()

    if armature is None or armature.type != "ARMATURE":
        return

    original_action = armature.animation_data.action
    empties = []

    deselect_all()
    scene.frame_set(scene.frame_start)

    # Instantiate plain axes helpers to track unscaled positional markers
    for pose_bone in armature.pose.bones:
        bpy.ops.object.empty_add(type="PLAIN_AXES", radius=0.1, location=(0, 0, 0))
        empty = bpy.context.active_object
        empty.name = pose_bone.name

        bpy.ops.object.constraint_add(type="CHILD_OF")
        empty.constraints["Child Of"].use_scale_x = False
        empty.constraints["Child Of"].use_scale_y = False
        empty.constraints["Child Of"].use_scale_z = False
        empty.constraints["Child Of"].target = armature
        empty.constraints["Child Of"].subtarget = pose_bone.name

        bcPrint(f"Baking transform trajectory for helper: {empty.name}...")
        bpy.ops.nla.bake(
            frame_start=scene.frame_start,
            frame_end=scene.frame_end,
            step=1,
            only_selected=True,
            visual_keying=True,
            clear_constraints=True,
            clear_parents=False,
            use_current_action=False,
            bake_types={"OBJECT"},
        )

        empty.animation_data.action.name += "+bcry"
        empties.append(empty)

    bcPrint("Positional markers successfully baked.")
    deselect_all()

    set_active(armature)
    armature.select_set(True)

    bpy.ops.object.transform_apply(rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.user_transforms_clear()

    # Re-constrain skeleton bones to track scale-corrected helpers
    for pose_bone in armature.pose.bones:
        pose_bone.constraints.new(type="COPY_LOCATION")
        pose_bone.constraints.new(type="COPY_ROTATION")

        for empty in empties:
            if empty.name == pose_bone.name:
                pose_bone.constraints["Copy Location"].target = empty
                pose_bone.constraints["Copy Rotation"].target = empty
                break

        pose_bone.bone.select = True

    bcPrint("Baking corrected scale animation back to skeleton...")
    bpy.ops.nla.bake(
        frame_start=scene.frame_start,
        frame_end=scene.frame_end,
        step=1,
        only_selected=True,
        visual_keying=True,
        clear_constraints=True,
        clear_parents=False,
        use_current_action=False,
        bake_types={"POSE"},
    )

    bpy.ops.object.mode_set(mode="OBJECT")

    armature.animation_data.action.name = original_action.name + "_scaled"
    armature.animation_data.action.use_fake_user = True

    deselect_all()

    bcPrint("Cleaning up plain axes animation trackers...")
    for empty in empties:
        empty.select_set(True)

    bpy.ops.object.delete()
    remove_unused_actions()

    bcPrint("Animation scale application completed successfully.")


def get_root_bone(armature):
    """Retrieves the root-most bone of the given armature structure."""
    for bone in get_bones(armature):
        if bone.parent is None:
            return bone
    return None


def count_root_bones(armature):
    """Counts the number of independent root hierarchies in the armature."""
    count = 0
    for bone in get_bones(armature):
        if bone.parent is None:
            count += 1
    return count


def get_armature_for_object(object_):
    """Identifies the armature parent controller associated with the mesh (supports modifier fallback)."""
    if object_.parent is not None and object_.parent.type == "ARMATURE":
        return object_.parent
    # Restored bypass for meshes not directly steamed in the outliner
    for mod in object_.modifiers:
        if mod.type == "ARMATURE" and mod.object:
            return mod.object
    return None


def get_armature():
    """Identifies the target export armature in the current scene context."""
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and obj.users_collection:
            for col in obj.users_collection:
                if col.name.endswith(".chr") or col.name.endswith(".skin"):
                    return obj

    # Fallback to any active or scene-bound armature
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    return None


def get_bones(armature):
    """Utility to quickly grab list of bone references from armature object data."""
    return [bone for bone in armature.data.bones]


def get_armature_from_node(group):
    """Returns the single armature reference from a target export node group."""
    armatures = [obj for obj in group.objects if obj.type == "ARMATURE"]
    armature_count = len(armatures)

    if armature_count == 1:
        return armatures[0]
    elif armature_count == 0:
        raise RuntimeError("Exporter Error: Export group has no parent armature!")
    else:
        raise RuntimeError("Exporter Error: Export group has more than one armature!")


def activate_all_bone_layers(armature):
    """Ensures all Blender bone collections are visible to ensure reliable bone transforms access."""
    layers = []
    for index in range(0, len(armature.data.collections_all)):
        layers.append(armature.data.collections_all[index].is_visible)
        armature.data.collections_all[index].is_visible = True

    return layers


def recover_bone_layers(armature, layers):
    """Restores pre-export visibility states of Blender bone collections."""
    for index in range(0, len(armature.data.collections_all)):
        armature.data.collections_all[index].is_visible = layers[index]
