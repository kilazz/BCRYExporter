# ------------------------------------------------------------------------------
# Name:        operators/bone_ops.py
# Purpose:     All operator classes related to bone and armature operations
# ------------------------------------------------------------------------------

import math
import bpy
import bmesh
from bpy.props import (
    BoolProperty,
    BoolVectorProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntVectorProperty,
    StringProperty,
)

# Modular package imports
from ..core.logger import bcPrint
from ..engine import constants
from .. import utils


class BCRY_OT_edit_inverse_kinematics(bpy.types.Operator):
    """Edit inverse kinematics properties for selected bone."""

    bl_label = "Edit Inverse Kinematics of Selected Bone"
    bl_idname = "bcry.edit_inverse_kinematics"

    info = "Force this bone proxy to be a {} primitive in the engine."

    proxy_type: EnumProperty(
        name="Physic Proxy",
        items=(
            ("box", "Box", info.format("Box")),
            ("cylinder", "Cylinder", info.format("Cylinder")),
            ("capsule", "Capsule", info.format("Capsule")),
            ("sphere", "Sphere", info.format("Sphere")),
        ),
        default="capsule",
    )

    is_rotation_lock: BoolVectorProperty(
        name="Rotation Lock  [X, Y, Z]:", description="Bone Rotation Lock X, Y, Z"
    )

    rotation_min: IntVectorProperty(
        name="Rot Limit Min:",
        description="Bone Rotation Minimum Limit X, Y, Z",
        default=(-180, -180, -180),
        min=-180,
        max=0,
    )

    rotation_max: IntVectorProperty(
        name="Rot Limit Max:",
        description="Bone Rotation Maximum Limit X, Y, Z",
        default=(180, 180, 180),
        min=0,
        max=180,
    )

    bone_spring: FloatVectorProperty(
        name="Spring  [X, Y, Z]:",
        description=constants.DESCRIPTIONS["spring"],
        default=(0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
    )

    bone_spring_tension: FloatVectorProperty(
        name="Spring Tension  [X, Y, Z]:",
        description=constants.DESCRIPTIONS["spring"],
        default=(1.0, 1.0, 1.0),
        min=-3.14159,
        max=3.14159,
    )

    bone_damping: FloatVectorProperty(
        name="Damping  [X, Y, Z]:",
        description=constants.DESCRIPTIONS["damping"],
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
    )

    bone = None

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "ARMATURE"
            or context.object.mode != "POSE"
        ):
            self.report({"ERROR"}, "Please select a bone in POSE mode!")
            return {"CANCELLED"}

        if context.active_pose_bone:
            self.bone = context.active_pose_bone
        else:
            self.report({"ERROR"}, "Please select a bone in POSE mode!")
            return {"CANCELLED"}

        if "phys_proxy" in self.bone:
            self.proxy_type = self.bone["phys_proxy"]

        self.is_rotation_lock[0] = self.bone.lock_ik_x
        self.is_rotation_lock[1] = self.bone.lock_ik_y
        self.is_rotation_lock[2] = self.bone.lock_ik_z

        self.rotation_min[0] = int(math.degrees(self.bone.ik_min_x))
        self.rotation_min[1] = int(math.degrees(self.bone.ik_min_y))
        self.rotation_min[2] = int(math.degrees(self.bone.ik_min_z))

        self.rotation_max[0] = int(math.degrees(self.bone.ik_max_x))
        self.rotation_max[1] = int(math.degrees(self.bone.ik_max_y))
        self.rotation_max[2] = int(math.degrees(self.bone.ik_max_z))

        if "Spring" in self.bone:
            self.bone_spring = self.bone["Spring"]
        if "Spring Tension" in self.bone:
            self.bone_spring_tension = self.bone["Spring Tension"]
        if "Damping" in self.bone:
            self.bone_damping = self.bone["Damping"]

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.bone is None:
            bcPrint("Please select a bone in pose mode!")
            return {"FINISHED"}

        self.bone["phys_proxy"] = self.proxy_type

        self.bone.lock_ik_x = self.is_rotation_lock[0]
        self.bone.lock_ik_y = self.is_rotation_lock[1]
        self.bone.lock_ik_z = self.is_rotation_lock[2]

        self.bone.ik_min_x = math.radians(self.rotation_min[0])
        self.bone.ik_min_y = math.radians(self.rotation_min[1])
        self.bone.ik_min_z = math.radians(self.rotation_min[2])

        self.bone.ik_max_x = math.radians(self.rotation_max[0])
        self.bone.ik_max_y = math.radians(self.rotation_max[1])
        self.bone.ik_max_z = math.radians(self.rotation_max[2])

        self.bone["Spring"] = self.bone_spring
        self.bone["Spring Tension"] = self.bone_spring_tension
        self.bone["Damping"] = self.bone_damping

        return {"FINISHED"}


class BCRY_OT_apply_animation_scale(bpy.types.Operator):
    """Select to apply animation skeleton scaling and rotation."""

    bl_label = "Apply Animation Scaling"
    bl_idname = "bcry.apply_animation_scaling"

    def execute(self, context):
        utils.apply_animation_scale(context.active_object)
        return {"FINISHED"}

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "ARMATURE"
            or context.object.mode != "OBJECT"
        ):
            self.report({"ERROR"}, "Select an armature in OBJECT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_add_root_bone(bpy.types.Operator):
    """Click to add a root bone to the active armature."""

    bl_label = "Add Root Bone"
    bl_idname = "bcry.add_root_bone"
    bl_options = {"REGISTER", "UNDO"}

    forward_direction: EnumProperty(
        name="Forward Direction",
        items=(
            ("y", "+Y", "The Locator Locomotion is faced to positive Y direction."),
            ("_y", "-Y", "The Locator Locomotion is faced to negative Y direction."),
            ("x", "+X", "The Locator Locomotion is faced to positive X direction."),
            ("_x", "-X", "The Locator Locomotion is faced to negative Y direction."),
            ("z", "+Z", "The Locator Locomotion is faced to positive Z direction."),
            ("_z", "-Z", "The Locator Locomotion is faced to negative Z direction."),
        ),
        default="y",
    )

    bone_length: FloatProperty(
        name="Bone Length",
        default=0.18,
        description=constants.DESCRIPTIONS["locator_length"],
    )
    root_name: StringProperty(name="Root Name", default="Root")
    hips_bone: StringProperty(name="Hips Bone", default="hips")

    def invoke(self, context, event):
        bones = [bone for bone in context.active_object.pose.bones]
        search_words = ["hips", "pelvis"]

        for bone in bones:
            for word in search_words:
                if word in bone.name.lower():
                    self.hips_bone = bone.name
        armature = context.active_object

        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Please select an armature object!")
            return {"CANCELLED"}
        elif armature.pose.bones.find(self.root_name) != -1:
            message = (
                f"{armature.name} armature already has a Root ({self.root_name}) bone!"
            )
            self.report({"INFO"}, message)
            return {"CANCELLED"}

        bpy.ops.object.mode_set(mode="EDIT")
        root_bone = utils.get_root_bone(armature)
        loc = root_bone.head
        if loc.x == 0 and loc.y == 0 and loc.z == 0:
            message = (
                "Armature seems to already have a root/center bone at ZERO location!"
            )
            self.report({"INFO"}, message)
            return {"CANCELLED"}
        else:
            self.hips_bone = root_bone.name

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        armature = context.active_object

        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.armature.select_all(action="DESELECT")
        bpy.ops.armature.bone_primitive_add(name=self.root_name)
        root_bone = armature.data.edit_bones[self.root_name]
        root_bone.select = True
        root_bone.select_head = True
        root_bone.select_tail = True

        # Supports Blender 4.x Bone Collections instead of legacy bone layers
        rootCollectionIndex = -1
        rootCollectionName = "bcry_root"
        for index in range(0, len(root_bone.collections)):
            collectionName = armature.data.collections_all[index].name
            bpy.ops.armature.collection_unassign_named(
                name=collectionName, bone_name=root_bone.name
            )
            if collectionName == rootCollectionName:
                rootCollectionIndex = index
        if rootCollectionIndex == -1:
            bpy.ops.armature.assign_to_collection(
                collection_index=-1, new_collection_name=rootCollectionName
            )
        else:
            bpy.ops.armature.assign_to_collection(rootCollectionIndex)
        armature.data.collections_all[rootCollectionName].is_visible = True

        root_bone.head.zero()
        root_bone.tail.zero()
        if self.forward_direction == "y":
            root_bone.tail.y = self.bone_length
        elif self.forward_direction == "_y":
            root_bone.tail.y = -self.bone_length
        elif self.forward_direction == "x":
            root_bone.tail.x = self.bone_length
        elif self.forward_direction == "_x":
            root_bone.tail.x = -self.bone_length
        elif self.forward_direction == "z":
            root_bone.tail.z = self.bone_length
        elif self.forward_direction == "_z":
            root_bone.tail.z = -self.bone_length

        armature.data.edit_bones[self.hips_bone].parent = root_bone

        bpy.ops.object.mode_set(mode="POSE")
        root_pose_bone = armature.pose.bones[self.root_name]
        root_pose_bone.bone.select = True
        armature.data.bones.active = root_pose_bone.bone

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"FINISHED"}


class BCRY_OT_add_locator_locomotion(bpy.types.Operator):
    """Add locator locomotion bone for movement in CryEngine."""

    bl_label = "Add Locator Locomotion"
    bl_idname = "bcry.add_locator_locomotion"
    bl_options = {"REGISTER", "UNDO"}

    forward_direction: EnumProperty(
        name="Forward Direction",
        items=(
            ("y", "+Y", "The Locator Locomotion is faced to positive Y direction."),
            ("_y", "-Y", "The Locator Locomotion is faced to negative Y direction."),
            ("x", "+X", "The Locator Locomotion is faced to positive X direction."),
            ("_x", "-X", "The Locator Locomotion is faced to negative Y direction."),
            ("z", "+Z", "The Locator Locomotion is faced to positive Z direction."),
            ("_z", "-Z", "The Locator Locomotion is faced to negative Z direction."),
        ),
        default="y",
    )

    bone_length: FloatProperty(
        name="Bone Length",
        default=0.5,
        description=constants.DESCRIPTIONS["locator_length"],
    )
    root_bone: StringProperty(
        name="Root Bone",
        default="Root",
        description=constants.DESCRIPTIONS["locator_root"],
    )
    movement_bone: StringProperty(
        name="Movement Bone",
        default="Bip01__Pelvis",
        description=constants.DESCRIPTIONS["locator_move"],
    )

    x_axis: BoolProperty(
        name="X Axis",
        default=False,
        description="Use X axis from movement reference bone.",
    )

    y_axis: BoolProperty(
        name="Y Axis",
        default=True,
        description="Use Y axis from movement reference bone.",
    )

    z_axis: BoolProperty(
        name="Z Axis",
        default=False,
        description="Use Z axis from movement reference bone.",
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "forward_direction")
        col.separator()

        col.prop(self, "bone_length")
        col.separator()

        col.prop(self, "root_bone")
        col.prop(self, "movement_bone")
        col.separator()

        col.label(text="Movement Axis:")
        col.prop(self, "x_axis")
        col.prop(self, "y_axis")
        col.prop(self, "z_axis")

    def invoke(self, context, event):
        armature = context.active_object
        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Please select an armature object!")
            return {"CANCELLED"}
        elif armature.pose.bones.find("Locator_Locomotion") != -1:
            message = f"{armature.name} armature already has a Locator Locomotion bone!"
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        root_bone = utils.get_root_bone(armature)
        self.root_bone = root_bone.name
        self.movement_bone = root_bone.children[0].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Please select an armature object!")
            return {"FINISHED"}

        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.armature.select_all(action="DESELECT")
        bpy.ops.armature.bone_primitive_add(name="Locator_Locomotion")
        locator_bone = armature.data.edit_bones["Locator_Locomotion"]
        locator_bone.select = True
        locator_bone.select_head = True
        locator_bone.select_tail = True

        # Assigns using standard 4.x Bone Collections instead of legacy bone layers
        rootCollectionIndex = -1
        rootCollectionName = "bcry_root"
        for index in range(0, len(locator_bone.collections)):
            collectionName = armature.data.collections_all[index].name
            bpy.ops.armature.collection_unassign_named(
                name=collectionName, bone_name=locator_bone.name
            )
            if collectionName == rootCollectionName:
                rootCollectionIndex = index
        if rootCollectionIndex == -1:
            bpy.ops.armature.assign_to_collection(
                collection_index=-1, new_collection_name=rootCollectionName
            )
        else:
            bpy.ops.armature.assign_to_collection(rootCollectionIndex)
        armature.data.collections_all[rootCollectionName].is_visible = True

        locator_bone.parent = armature.data.edit_bones[self.root_bone]
        locator_bone.head.zero()
        locator_bone.tail = locator_bone.head
        if self.forward_direction == "y":
            locator_bone.tail.y += self.bone_length
        elif self.forward_direction == "_y":
            locator_bone.tail.y += -self.bone_length
        elif self.forward_direction == "x":
            locator_bone.tail.x += self.bone_length
        elif self.forward_direction == "_x":
            locator_bone.tail.x += -self.bone_length
        elif self.forward_direction == "z":
            locator_bone.tail.z += self.bone_length
        elif self.forward_direction == "_z":
            locator_bone.tail.z += -self.bone_length

        movement_bone = armature.data.edit_bones[self.movement_bone]

        bpy.ops.object.mode_set(mode="POSE")
        locator_pose_bone = armature.pose.bones["Locator_Locomotion"]
        locator_pose_bone.bone.select = True
        armature.data.bones.active = locator_pose_bone.bone

        locator_pose_bone.constraints.new(type="COPY_LOCATION")
        copy_location = locator_pose_bone.constraints["Copy Location"]
        copy_location.target = armature
        copy_location.subtarget = self.movement_bone
        copy_location.use_x = self.x_axis
        copy_location.use_y = self.y_axis
        copy_location.use_z = self.z_axis
        copy_location.use_offset = True

        if self.x_axis:
            locator_pose_bone.location[0] = -1 * movement_bone.head.x
        if self.y_axis:
            locator_pose_bone.location[1] = -1 * movement_bone.head.y
        if self.z_axis:
            locator_pose_bone.location[2] = -1 * movement_bone.head.z
        locator_pose_bone.keyframe_insert("location", frame=1)

        for child in locator_pose_bone.parent.children:
            if (
                child.name != locator_pose_bone.name
                and child.name != self.movement_bone
            ):
                child.constraints.new(type="COPY_LOCATION")
                copy_location = child.constraints["Copy Location"]
                copy_location.target = armature
                copy_location.subtarget = locator_pose_bone.name
                copy_location.use_x = True
                copy_location.use_y = True
                copy_location.use_z = True
                copy_location.use_offset = True

                child.constraints.new(type="COPY_ROTATION")
                copy_rotation = child.constraints["Copy Rotation"]
                copy_rotation.target = armature
                copy_rotation.subtarget = locator_pose_bone.name
                copy_rotation.use_x = True
                copy_rotation.use_y = True
                copy_rotation.use_z = True
                copy_rotation.mix_mode = "AFTER"

        return {"FINISHED"}


class BCRY_OT_add_primitive_mesh(bpy.types.Operator):
    """Add primitive mesh for active skeleton."""

    bl_label = "Add Primitive Mesh"
    bl_idname = "bcry.add_primitive_mesh"
    bl_options = {"REGISTER", "UNDO"}

    root_bone: StringProperty(
        name="Root Bone",
        default="Root",
        description=constants.DESCRIPTIONS["locator_root"],
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "root_bone")
        col.separator()

    def invoke(self, context, event):
        armature = context.active_object
        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Please select an armature object!")
            return {"CANCELLED"}
        root_bone = utils.get_root_bone(armature)
        self.root_bone = root_bone.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Please select an armature object!")
            return {"FINISHED"}

        x = context.view_layer.layer_collection
        context.view_layer.active_layer_collection = x

        bpy.ops.mesh.primitive_plane_add()
        triangle = context.active_object

        bm = bmesh.new()
        bm.verts.new((1.0, 1.0, 0.0))
        bm.verts.new((-1.0, -1.0, 0.0))
        bm.verts.new((1.0, -1.0, 0.0))

        bm.faces.new(bm.verts)
        bm.to_mesh(triangle.data)
        triangle.name = "No_Draw"
        triangle.data.name = "No_Draw"

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all()
        bpy.ops.object.vertex_group_assign_new()
        triangle.vertex_groups[0].name = self.root_bone
        bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.modifier_add(type="ARMATURE")
        triangle.modifiers["Armature"].object = armature
        triangle.parent = armature

        material_ = None
        mat_name = f"{armature.name}__01__No_Draw__physProxyNoDraw"

        if mat_name in bpy.data.materials:
            material_ = bpy.data.materials[mat_name]
        else:
            material_ = bpy.data.materials.new(mat_name)

        if triangle.material_slots:
            triangle.material_slots[0].material = material_
        else:
            bpy.ops.object.material_slot_add()
            if triangle.material_slots:
                triangle.material_slots[0].material = material_

        if len(triangle.users_collection) > 0:
            for c in list(triangle.users_collection):
                c.objects.unlink(triangle)

        for c in armature.users_collection:
            if not utils.is_export_node(c):
                c.objects.link(triangle)
                break

        utils.set_active(triangle)
        return {"FINISHED"}


class BCRY_OT_physicalize_skeleton(bpy.types.Operator):
    """Create physic skeleton and physical proxies for bones."""

    bl_label = "Physicalize Skeleton"
    bl_idname = "bcry.physicalize_skeleton"
    bl_options = {"REGISTER", "UNDO"}

    physic_skeleton: BoolProperty(
        name="Physic Skeleton", default=True, description="Creates physic skeleton."
    )
    physic_proxies: BoolProperty(
        name="Physic Proxies", default=True, description="Creates physic proxies."
    )
    physic_proxy_settings: BoolProperty(
        name="Physic Proxy Settings",
        default=True,
        description="Fill physic proxy settings to default.",
    )
    physic_ik_settings: BoolProperty(
        name="IK Settings", default=True, description="Fill IK settings to default."
    )
    radius_torso: FloatProperty(
        name="Torso Radius",
        default=0.12,
        min=0.01,
        precision=3,
        step=0.1,
        description="Torso bones radius",
    )
    radius_head: FloatProperty(
        name="Head Radius",
        default=0.1,
        min=0.01,
        precision=3,
        step=0.1,
        description="Head bones radius",
    )
    radius_arm: FloatProperty(
        name="Arm Radius",
        default=0.04,
        min=0.01,
        precision=3,
        step=0.1,
        description="Arm bones radius",
    )
    radius_leg: FloatProperty(
        name="Leg Radius",
        default=0.05,
        min=0.01,
        precision=3,
        step=0.1,
        description="Leg bones radius",
    )
    radius_foot: FloatProperty(
        name="Foot Radius",
        default=0.05,
        min=0.01,
        precision=3,
        step=0.1,
        description="Foot bones radius",
    )
    radius_other: FloatProperty(
        name="Other Radius",
        default=0.05,
        min=0.01,
        precision=3,
        step=0.1,
        description="Other bones radius",
    )
    physic_materials: BoolProperty(
        name="Create Physic Materials",
        default=True,
        description="Creates materials for bone proxies.",
    )
    physic_alpha: FloatProperty(
        name="Physic Alpha",
        default=0.2,
        min=0.0,
        max=1.0,
        step=1.0,
        description="Set physic proxy alpha value.",
    )
    use_single_material: BoolProperty(
        name="Use Single Material",
        default=False,
        description="Use single material for all bone proxies.",
    )

    def invoke(self, context, event):
        armature = context.active_object
        if armature.type != "ARMATURE":
            self.report({"ERROR"}, "You have to select a armature object!")
            return {"CANCELLED"}
        group = utils.get_chr_node_from_skeleton(armature)
        if not group:
            self.report(
                {"ERROR"},
                "Your armature has to has a primitive mesh which added to a CHR node!",
            )
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Physicalize Options:")
        col.prop(self, "physic_skeleton")
        col.prop(self, "physic_proxies")
        col.prop(self, "physic_proxy_settings")
        col.prop(self, "physic_ik_settings")
        col.separator()

        col.label(text="Physic Proxy Sizes:")
        col.prop(self, "radius_torso")
        col.prop(self, "radius_head")
        col.prop(self, "radius_arm")
        col.prop(self, "radius_leg")
        col.prop(self, "radius_foot")
        col.prop(self, "radius_other")
        col.separator()
        col.separator()

        col.label(text="Physic Materials:")
        col.prop(self, "physic_materials")
        col.prop(self, "physic_alpha")
        col.prop(self, "use_single_material")
        col.separator()
        col.separator()

    def execute(self, context):
        x = context.view_layer.layer_collection
        context.view_layer.active_layer_collection = x

        armature = context.active_object
        armature_collection = armature.users_collection[0]
        materials = {}
        collection = utils.get_chr_node_from_skeleton(armature)
        self.__create_materials(armature, materials)
        armature.data.pose_position = "REST"
        bpy.ops.object.mode_set(mode="EDIT")

        for bone in armature.pose.bones:
            if not bone.bone.select:
                continue

            if self.physic_proxies:
                name = f"{bone.name}_boneGeometry"
                bone_radius = {
                    "torso": self.radius_torso,
                    "head": self.radius_head,
                    "arm": self.radius_arm,
                    "leg": self.radius_leg,
                    "foot": self.radius_foot,
                    "other": self.radius_other,
                }
                bone_type = utils.get_bone_type(bone)
                rd = bone_radius[bone_type]

                bpy.ops.mesh.primitive_cube_add(size=rd, location=(0, 0, 0))
                object_ = context.active_object
                object_.name = name
                object_.data.name = name

                bpy.ops.object.mode_set(mode="EDIT")
                bm = bmesh.from_edit_mesh(object_.data)
                scale_vector = (2.07, 2.07, 2.07)

                for face in bm.faces:
                    if face.normal.x == -1.0:
                        for vert in face.verts:
                            vert.co.x = 0.0
                    elif face.normal.x == 1.0:
                        for vert in face.verts:
                            vert.co.x = bone.length
                        bmesh.ops.scale(bm, vec=scale_vector, verts=face.verts)

                bpy.ops.object.mode_set(mode="OBJECT")
                object_.matrix_world = utils.transform_animation_matrix(bone.matrix)

                if collection:
                    collection.objects.link(object_)

                for c in list(object_.users_collection):
                    if c != collection:
                        c.objects.unlink(object_)

                object_.show_transparent = True
                object_.show_wire = True

                if self.physic_materials:
                    mat = None
                    if self.use_single_material:
                        mat = materials["single"]
                    else:
                        mat = materials[utils.get_bone_material_type(bone, bone_type)]

                    mat.alpha_threshold = self.physic_alpha
                    # Fixed original typo where 'object_.material_slot' was called instead of material_slots
                    if object_.material_slots:
                        object_.material_slots[0].material = mat
                    else:
                        bpy.ops.object.material_slot_add()
                        if object_.material_slots:
                            object_.material_slots[0].material = mat

                    if not object_.data.uv_layers:
                        object_.data.uv_layers.new()

                object_.select_set(False)

                if self.physic_proxy_settings:
                    if bone_type == "spine" or bone_type == "head":
                        bone["phys_proxy"] = "sphere"
                    elif (
                        bone_type == "arm" or bone_type == "leg" or bone_type == "foot"
                    ):
                        bone["phys_proxy"] = "capsule"
                    else:
                        bone["phys_proxy"] = "capsule"

                    bone["Spring"] = (0.0, 0.0, 0.0)
                    bone["Spring Tension"] = (1.0, 1.0, 1.0)
                    bone["Damping"] = (1.0, 1.0, 1.0)

                    hips_list = ["hips", "pelvis"]
                    if utils.is_in_list(bone.name, hips_list):
                        bone["Damping"] = (0.0, 0.0, 0.0)

                if self.physic_ik_settings:
                    self.__set_ik(bone)

        if self.physic_skeleton:
            bpy.ops.object.mode_set(mode="OBJECT")
            context.view_layer.objects.active = armature
            armature.select_set(True)
            bpy.ops.object.duplicate()
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.armature.select_all(action="INVERT")
            bpy.ops.armature.delete()
            bpy.ops.object.mode_set(mode="OBJECT")

            armature_name = f"{armature.name}.001"
            physic_name = f"{armature.name}_Phys"
            armature.select_set(False)
            location = armature.location.copy()
            location.x -= 1.63

            physic_armature = bpy.data.objects[armature_name]
            physic_armature.name = physic_name
            physic_armature.data.name = physic_name
            physic_armature.users_collection[0].objects.unlink(physic_armature)
            armature_collection.objects.link(physic_armature)

            physic_armature.select_set(True)
            context.view_layer.objects.active = physic_armature

            physic_armature.location = location
            physic_armature.display_type = "WIRE"

            for bone in physic_armature.data.bones:
                utils.make_physic_bone(bone)

            physic_armature.select_set(False)

        self.__set_primitive_mesh_material(armature, materials)

        armature.select_set(True)
        context.view_layer.objects.active = armature
        armature.data.pose_position = "POSE"

        return {"FINISHED"}

    def __check_parent_relations(self, armature, physic_armature):
        for phys_bone in physic_armature.pose.bones:
            if not phys_bone.parent:
                bone_name = phys_bone.name[:-5]
                bone = armature.pose.bones[bone_name]
                while True:
                    if bone.parent is None:
                        break

                    bone = bone.parent
                    phys_bone_name = f"{bone.name}_Phys"
                    if phys_bone_name in physic_armature.pose.bones:
                        phys_edit_bone = physic_armature.data.edit_bones[phys_bone.name]
                        phys_parent_edit_bone = physic_armature.data.edit_bones[
                            phys_bone_name
                        ]
                        phys_edit_bone.parent = phys_parent_edit_bone
                        break

    def __set_primitive_mesh_material(self, armature, materials):
        object_ = utils.get_chr_object_from_skeleton(armature)
        object_.select_set(True)
        # Replaced undefined variable 'context' with 'bpy.context' to satisfy Ruff F821
        bpy.context.view_layer.objects.active = object_
        mat = None
        if self.use_single_material:
            mat = materials["single"]
        else:
            mat = materials["primitive"]

        if object_.material_slots:
            object_.material_slots[0].material = mat
        else:
            bpy.ops.object.material_slot_add()
            if object_.material_slots:
                object_.material_slots[0].material = mat

        object_.select_set(False)

    def __create_materials(self, armature, materials):
        if self.use_single_material:
            single_material_name = f"{armature.name}__01__proxy_bones__physProxyNoDraw"
            if single_material_name in bpy.data.materials:
                materials["single"] = bpy.data.materials[single_material_name]
            else:
                materials["single"] = bpy.data.materials.new(single_material_name)

            materials["single"].diffuse_color = (0.016, 0.016, 0.016)
            return

        mat_names = {
            "primitive": f"{armature.name}__01__No_Draw__physProxyNoDraw",
            "larm": f"{armature.name}__02__Skel_Arm_Left__physProxyNoDraw",
            "rarm": f"{armature.name}__03__Skel_Arm_Right__physProxyNoDraw",
            "lleg": f"{armature.name}__04__Skel_Leg_Left__physProxyNoDraw",
            "rleg": f"{armature.name}__05__Skel_Leg_Right__physProxyNoDraw",
            "torso": f"{armature.name}__06__Skel_Torso__physProxyNoDraw",
            "head": f"{armature.name}__07__Skel_Head__physProxyNoDraw",
            "lfoot": f"{armature.name}__08__Skel_Foot_Left__physProxyNoDraw",
            "rfoot": f"{armature.name}__09__Skel_Foot_Right__physProxyNoDraw",
        }

        for key, value in mat_names.items():
            if value in bpy.data.materials:
                materials[key] = bpy.data.materials[value]
            else:
                materials[key] = bpy.data.materials.new(value)

        materials["larm"].diffuse_color = (0.800, 0.008, 0.019, 0.5)
        materials["rarm"].diffuse_color = (1.000, 0.774, 0.013, 0.5)
        materials["lleg"].diffuse_color = (0.023, 0.114, 1.000, 0.5)
        materials["rleg"].diffuse_color = (0.013, 1.000, 0.048, 0.5)
        materials["torso"].diffuse_color = (0.016, 0.016, 0.016, 0.5)
        materials["head"].diffuse_color = (0.000, 0.450, 0.464, 0.5)
        materials["lfoot"].diffuse_color = (1.000, 0.000, 0.632, 0.5)
        materials["rfoot"].diffuse_color = (1.000, 0.32, 0.093, 0.5)

    def __set_ik(self, bone):
        if utils.is_in_list(bone.name, ["spine"]):
            bone.lock_ik_x = False
            bone.lock_ik_y = False
            bone.lock_ik_z = False
            bone.ik_min_x = math.radians(-18)
            bone.ik_min_y = math.radians(-18)
            bone.ik_min_z = math.radians(-18)
            bone.ik_max_x = math.radians(18)
            bone.ik_max_y = math.radians(18)
            bone.ik_max_z = math.radians(18)

        elif utils.is_in_list(bone.name, ["head"]):
            bone.lock_ik_x = False
            bone.lock_ik_y = False
            bone.lock_ik_z = False
            bone.ik_min_x = math.radians(-30)
            bone.ik_min_y = math.radians(-70)
            bone.ik_min_z = math.radians(-20)
            bone.ik_max_x = math.radians(30)
            bone.ik_max_y = math.radians(70)
            bone.ik_max_z = math.radians(20)

        elif utils.is_in_list(bone.name, ["upperarm"]):
            bone.lock_ik_x = False
            bone.lock_ik_y = True
            bone.lock_ik_z = False
            bone.ik_min_x = math.radians(-60)
            bone.ik_min_y = math.radians(-180)
            bone.ik_min_z = math.radians(
                -90 if utils.is_in_list(bone.name, ["left", ".l"]) else -140
            )
            bone.ik_max_x = math.radians(120)
            bone.ik_max_y = math.radians(180)
            bone.ik_max_z = math.radians(
                140 if utils.is_in_list(bone.name, ["left", ".l"]) else 90
            )

        elif utils.is_in_list(bone.name, ["forearm"]):
            bone.lock_ik_x = False
            bone.lock_ik_y = True
            bone.lock_ik_z = True
            bone.ik_min_x = math.radians(-34)
            bone.ik_min_y = math.radians(-180)
            bone.ik_min_z = math.radians(-180)
            bone.ik_max_x = math.radians(120)
            bone.ik_max_y = math.radians(180)
            bone.ik_max_z = math.radians(180)

        elif utils.is_in_list(bone.name, ["thigh"]):
            bone.lock_ik_x = False
            bone.lock_ik_y = True
            bone.lock_ik_z = False
            bone.ik_min_x = math.radians(-90)
            bone.ik_min_y = math.radians(-180)
            bone.ik_min_z = math.radians(
                -90 if utils.is_in_list(bone.name, ["left", ".l"]) else -60
            )
            bone.ik_max_x = math.radians(80)
            bone.ik_max_y = math.radians(180)
            bone.ik_max_z = math.radians(
                60 if utils.is_in_list(bone.name, ["left", ".l"]) else 90
            )

        elif utils.is_in_list(bone.name, ["calf"]):
            bone.lock_ik_x = False
            bone.lock_ik_y = True
            bone.lock_ik_z = True
            bone.ik_min_x = math.radians(0)
            bone.ik_min_y = math.radians(-180)
            bone.ik_min_z = math.radians(-180)
            bone.ik_max_x = math.radians(120)
            bone.ik_max_y = math.radians(180)
            bone.ik_max_z = math.radians(180)

        elif utils.is_in_list(bone.name, ["foot"]):
            bone.lock_ik_x = False
            bone.lock_ik_y = False
            bone.lock_ik_z = False
            bone.ik_min_x = math.radians(-60)
            bone.ik_min_y = math.radians(-4)
            bone.ik_min_z = math.radians(-30)
            bone.ik_max_x = math.radians(15)
            bone.ik_max_y = math.radians(4)
            bone.ik_max_z = math.radians(30)

        else:
            bone.lock_ik_x = False
            bone.lock_ik_y = False
            bone.lock_ik_z = False
            bone.ik_min_x = math.radians(-180)
            bone.ik_min_y = math.radians(-180)
            bone.ik_min_z = math.radians(-180)
            bone.ik_max_x = math.radians(180)
            bone.ik_max_y = math.radians(180)
            bone.ik_max_z = math.radians(180)


class BCRY_OT_clear_skeleton_physics(bpy.types.Operator):
    """Clear physics from selected skeleton."""

    bl_label = "Clear Skeleton Physics"
    bl_idname = "bcry.clear_skeleton_physics"
    bl_options = {"REGISTER", "UNDO"}

    physic_skeleton: BoolProperty(
        name="Remove Physic Skeleton",
        default=True,
        description="Removes physic skeleton.",
    )
    physic_proxies: BoolProperty(
        name="Clear Physic Proxies", default=True, description="Clears physic proxies."
    )

    def invoke(self, context, event):
        armature = context.active_object
        if armature.type != "ARMATURE":
            self.report({"ERROR"}, "You have to select a armature object!")
            return {"CANCELLED"}
        group = utils.get_chr_node_from_skeleton(armature)
        if not group:
            self.report(
                {"ERROR"},
                "Your armature has to has a primitive mesh which added to a CHR node!",
            )
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Dephysicalize Options:")
        col.prop(self, "physic_skeleton")
        col.prop(self, "physic_proxies")
        col.separator()
        col.separator()

    def execute(self, context):
        armature = context.active_object
        physic_armature = None
        physic_name = f"{armature.name}_Phys"
        group = utils.get_chr_node_from_skeleton(armature)

        if self.physic_proxies and group:
            armature.select_set(False)
            for object_ in group.objects:
                if utils.is_bone_geometry(object_):
                    object_.select_set(True)
                    context.view_layer.objects.active = object_
            bpy.ops.object.delete()

        if self.physic_skeleton and (physic_name in bpy.data.objects):
            physic_armature = bpy.data.objects[physic_name]
            armature.select_set(False)
            physic_armature.select_set(True)
            context.view_layer.objects.active = physic_armature
            bpy.ops.object.delete()

        return {"FINISHED"}


class BCRY_OT_rebuild_armature(bpy.types.Operator):
    """Rebuild armature to fix export errors."""

    bl_label = "Rebuild Armature"
    bl_idname = "bcry.rebuild_armature"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        armature = context.active_object
        utils.rebuild_armature(armature)
        return {"FINISHED"}


# Expose classes to operators/__init__.py dynamically
classes = (
    BCRY_OT_edit_inverse_kinematics,
    BCRY_OT_apply_animation_scale,
    BCRY_OT_add_root_bone,
    BCRY_OT_add_locator_locomotion,
    BCRY_OT_add_primitive_mesh,
    BCRY_OT_physicalize_skeleton,
    BCRY_OT_clear_skeleton_physics,
    BCRY_OT_rebuild_armature,
)
