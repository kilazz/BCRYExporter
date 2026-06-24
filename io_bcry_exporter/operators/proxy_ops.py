# ------------------------------------------------------------------------------
# Name:        operators/proxy_ops.py
# Purpose:     All operator classes related to physics proxies, joints, and UDPs
# ------------------------------------------------------------------------------

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty

# Modular package imports
from ..core.logger import bcPrint
from ..engine import constants, udp
from .. import utils


# ------------------------------------------------------------------------------
# Branching Helpers (Local to Proxy Context)
# ------------------------------------------------------------------------------


def get_vertex_data():
    """Helper to collect absolute coordinates of selected mesh vertices in Edit mode."""
    old_mode = bpy.context.active_object.mode
    bpy.ops.object.mode_set(mode="OBJECT")
    selected_vert_coordinates = [
        i.co for i in bpy.context.active_object.data.vertices if i.select
    ]
    bpy.ops.object.mode_set(mode=old_mode)
    return selected_vert_coordinates


def name_branch(is_new_branch):
    """Generates unique names for vegetation branch and joint helper elements."""
    highest_branch_number = 0
    highest_joint_number = {}
    for obj in bpy.data.objects:
        if (obj.type == "EMPTY") and ("branch" in obj.name):
            branch_components = obj.name.split("_")
            if branch_components:
                branch_name = branch_components[0]
                branch_number = int(branch_name[6:])
                joint_number = int(branch_components[1])
                if branch_number > highest_branch_number:
                    highest_branch_number = branch_number
                    highest_joint_number[branch_number] = joint_number
                if joint_number > highest_joint_number[branch_number]:
                    highest_joint_number[branch_number] = joint_number
    if highest_branch_number != 0:
        if is_new_branch:
            return f"branch{highest_branch_number + 1}_1"
        else:
            return f"branch{highest_branch_number}_{highest_joint_number[highest_branch_number] + 1}"
    else:
        return "branch1_1"


# ------------------------------------------------------------------------------
# Operators
# ------------------------------------------------------------------------------


class BCRY_OT_add_proxy(bpy.types.Operator):
    """Add proxy to selected mesh."""

    bl_label = "Add Proxy"
    bl_idname = "bcry.add_proxy"

    type_: StringProperty()
    child_: BoolProperty()
    errorReport = None

    def execute(self, context):
        save_objs = []
        active_object = bpy.context.active_object
        for obj in context.selected_objects:
            self.__add_proxy(obj)
            save_objs.append(obj)

        for obj in save_objs:
            obj.select_set(True)
        utils.set_active(active_object)

        message = f"Adding {self.type_} proxy to active object"
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def __add_proxy(self, object_):
        exportNode = None
        for collection in object_.users_collection:
            if utils.is_export_node(collection):
                if exportNode is None:
                    exportNode = collection
                else:
                    self.report(
                        {"ERROR"}, f"Object {object_.name} is in multiple export nodes!"
                    )
                    return {"CANCELLED"}
        if exportNode is None:
            self.report({"ERROR"}, f"Object {object_.name} is not in any export node!")
            return {"CANCELLED"}

        bpy.ops.object.select_all(action="DESELECT")
        object_.select_set(True)
        old_origin = object_.location.copy()
        old_cursor = bpy.context.scene.cursor.location.copy()
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
        bpy.ops.object.select_all(action="DESELECT")

        bpy.ops.mesh.primitive_cube_add()
        bound_box = bpy.context.active_object
        bound_box.name = f"{object_.name}_{self.type_}-proxy"
        bound_box.display_type = "WIRE"

        bound_box.dimensions = object_.dimensions
        bound_box.location = object_.location
        bound_box.rotation_euler = object_.rotation_euler

        # Replaced deprecated uv_texture_add with standard uv_layers.new
        if not bound_box.data.uv_layers:
            bound_box.data.uv_layers.new()

        if self.child_:
            bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
        else:
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        name = f"{utils.get_node_name(exportNode)}__99__proxy__physProxyNoDraw"
        if name in bpy.data.materials:
            proxy_material = bpy.data.materials[name]
        else:
            proxy_material = bpy.data.materials.new(name)
        bound_box.data.materials.append(proxy_material)

        bound_box["phys_proxy"] = self.type_

        bpy.context.scene.cursor.location = old_origin
        bpy.ops.object.select_all(action="DESELECT")
        object_.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        object_.select_set(False)
        bound_box.select_set(True)
        utils.set_active(bound_box)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        bpy.context.scene.cursor.location = old_cursor

        if len(bound_box.users_collection) > 0:
            for c in list(bound_box.users_collection):
                c.objects.unlink(bound_box)

        object_.users_collection[0].objects.link(bound_box)
        bpy.ops.object.select_all(action="DESELECT")

        if self.child_:
            bound_box.parent = object_
            bound_box.location = (0, 0, 0)
            bound_box.rotation_euler = (0, 0, 0)
            bound_box.scale = (1, 1, 1)

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "MESH"
            or context.object.mode != "OBJECT"
        ):
            self.report({"ERROR"}, "Select a mesh in OBJECT mode.")
            return {"CANCELLED"}
        return self.execute(context)


class BCRY_OT_add_mesh_proxy(bpy.types.Operator):
    """Click to add proxy to selected mesh."""

    bl_label = "Add Mesh Proxy"
    bl_idname = "bcry.add_mesh_proxy"

    child_: BoolProperty()
    separate_: BoolProperty()

    def execute(self, context):
        save_objs = []
        active_object = bpy.context.active_object
        save_mode = "OBJECT"
        if context.mode == "EDIT_MESH":
            for obj in context.selected_objects:
                self.__add_separate_proxy(obj)
                save_objs.append(obj)
            save_mode = "EDIT"
        else:
            for obj in context.selected_objects:
                self.__add_object_proxy(obj)
                save_objs.append(obj)

        for obj in save_objs:
            obj.select_set(True)
        utils.set_active(active_object)
        bpy.ops.object.mode_set(mode=save_mode)

        message = "Adding mesh proxy to active object"
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def __add_object_proxy(self, object_):
        bpy.ops.object.select_all(action="DESELECT")
        object_.select_set(True)
        utils.set_active(object_)

        bpy.ops.object.duplicate()
        mesh_collision = bpy.context.active_object
        mesh_collision.name = f"{object_.name}_mesh-proxy"
        mesh_collision.display_type = "WIRE"

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.mark_sharp(clear=True)
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")

        mesh_collision.data.materials.clear()
        name = "proxy"
        if name in bpy.data.materials:
            proxy_material = bpy.data.materials[name]
        else:
            proxy_material = bpy.data.materials.new(name)

        mesh_collision.data.materials.append(proxy_material)
        mesh_collision["phys_proxy"] = "notaprim"

        if self.child_:
            mesh_collision.parent = object_
            mesh_collision.location = (0, 0, 0)
            mesh_collision.rotation_euler = (0, 0, 0)
            mesh_collision.scale = (1, 1, 1)

        if self.separate_:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.separate(type="LOOSE")
            bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.select_all(action="DESELECT")

    def __add_separate_proxy(self, object_):
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        object_.select_set(True)

        if any(v.select for v in object_.data.vertices):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.duplicate()
            bpy.ops.mesh.separate(type="SELECTED")
            bpy.ops.object.mode_set(mode="OBJECT")
        else:
            return

        object_.select_set(False)
        mesh_collision = bpy.context.selected_objects[0]
        utils.set_active(mesh_collision)

        mesh_collision.name = f"{object_.name}_mesh-proxy"
        mesh_collision.display_type = "WIRE"

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.mark_sharp(clear=True)
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")

        mesh_collision.data.materials.clear()
        name = "proxy"
        if name in bpy.data.materials:
            proxy_material = bpy.data.materials[name]
        else:
            proxy_material = bpy.data.materials.new(name)

        mesh_collision.data.materials.append(proxy_material)
        mesh_collision["phys_proxy"] = "notaprim"
        bpy.ops.object.select_all(action="DESELECT")

        if self.child_:
            mesh_collision.parent = object_
            mesh_collision.location = (0, 0, 0)
            mesh_collision.rotation_euler = (0, 0, 0)
            mesh_collision.scale = (1, 1, 1)

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "MESH"
            or context.object.mode not in ["OBJECT", "EDIT"]
        ):
            self.report({"ERROR"}, "Select a mesh in OBJECT or EDIT mode.")
            return {"FINISHED"}
        return self.execute(context)


class BCRY_OT_add_breakable_joint(bpy.types.Operator):
    """Add a dummy helper breakable joint to 3D cursor position."""

    bl_label = "Add Breakable Joint"
    bl_idname = "bcry.add_breakable_joint"

    draw_size: FloatProperty(
        name="Joint Size", default=0.1, description="Breakable Joint Size"
    )

    is_limit: BoolProperty(
        name="Use Limit Property",
        default=True,
        description="Enable joint limit parameters.",
    )
    limit: FloatProperty(
        name="Limit", default=10.0, description=constants.DESCRIPTIONS["limit"]
    )

    is_bend: BoolProperty(
        name="Use Bend Property", description="Enable joint bending properties."
    )
    bend: FloatProperty(name="Bend", description=constants.DESCRIPTIONS["bend"])

    is_twist: BoolProperty(
        name="Use Twist Property", description="Enable joint twisting limits."
    )
    twist: FloatProperty(name="Twist", description=constants.DESCRIPTIONS["twist"])

    is_pull: BoolProperty(
        name="Use Pull Property", description="Enable joint tension pull constants."
    )
    pull: FloatProperty(name="Pull", description=constants.DESCRIPTIONS["pull"])

    is_push: BoolProperty(
        name="Use Push Property", description="Enable joint push factors."
    )
    push: FloatProperty(name="Push", description=constants.DESCRIPTIONS["push"])

    is_shift: BoolProperty(
        name="Use Shift Property", description="Enable shifting threshold properties."
    )
    shift: FloatProperty(name="Shift", description=constants.DESCRIPTIONS["shift"])

    player_can_break: BoolProperty(
        name="Player can break", description=constants.DESCRIPTIONS["player_can_break"]
    )
    gameplay_critical: BoolProperty(
        name="Gameplay critical",
        description=constants.DESCRIPTIONS["gameplay_critical"],
    )

    object_ = None
    collection_ = None

    def execute(self, context):
        bpy.ops.object.empty_add(type="CUBE")
        joint_ = bpy.context.active_object

        joint_.name = utils.get_joint_name(self.object_)
        joint_.parent = self.object_
        if self.collection_ not in joint_.users_collection:
            self.collection_.objects.link(joint_)

        udp.edit_udp(joint_, "limit", self.limit, self.is_limit)
        udp.edit_udp(joint_, "bend", self.bend, self.is_bend)
        udp.edit_udp(joint_, "twist", self.twist, self.is_twist)
        udp.edit_udp(joint_, "pull", self.pull, self.is_pull)
        udp.edit_udp(joint_, "push", self.push, self.is_push)
        udp.edit_udp(joint_, "shift", self.shift, self.is_shift)
        udp.edit_udp(
            joint_, "player_can_break", "player_can_break", self.player_can_break
        )
        udp.edit_udp(
            joint_, "gameplay_critical", "gameplay_critical", self.gameplay_critical
        )

        joint_.empty_display_size = self.draw_size
        return {"FINISHED"}

    def invoke(self, context, event):
        self.object_ = bpy.context.active_object
        message = (
            "Please select an empty helper assigned to an active BCRY export node."
        )
        if self.object_ is None or self.object_.type != "EMPTY":
            self.report({"ERROR"}, message)
            return {"FINISHED"}

        for collection in self.object_.users_collection:
            if (
                utils.is_export_node(collection)
                and utils.get_node_type(collection) == "cgf"
            ):
                self.collection_ = collection
                return context.window_manager.invoke_props_dialog(self)

        self.report({"ERROR"}, message)
        return {"FINISHED"}


class BCRY_OT_add_branch(bpy.types.Operator):
    """Click to add a branch at active vertex or first vertex in a set of vertices."""

    bl_label = "Add Branch"
    bl_idname = "bcry.add_branch"

    def execute(self, context):
        x = context.view_layer.layer_collection
        context.view_layer.active_layer_collection = x

        active_object = context.active_object
        bpy.ops.object.mode_set(mode="OBJECT")
        selected_vert_coordinates = get_vertex_data()

        if selected_vert_coordinates:
            selected_vert = selected_vert_coordinates[0]
            bpy.ops.object.add(
                radius=0.25,
                type="EMPTY",
                enter_editmode=False,
                align="WORLD",
                location=(selected_vert[0], selected_vert[1], selected_vert[2]),
            )
            empty_object = context.active_object
            empty_object.name = name_branch(True)

            empty_object.users_collection[0].objects.unlink(empty_object)
            active_object.users_collection[0].objects.link(empty_object)
            empty_object.parent = active_object

            utils.set_active(active_object)
            bpy.ops.object.mode_set(mode="EDIT")

            bcPrint("Added new vegetation branch hook.")
        return {"FINISHED"}

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "MESH"
            or context.object.mode != "EDIT"
            or not get_vertex_data()
        ):
            self.report({"ERROR"}, "Select a vertex in EDIT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_add_branch_joint(bpy.types.Operator):
    """Click to add a branch joint at selected vertex or first vertex in a set of vertices."""

    bl_label = "Add Branch Joint"
    bl_idname = "bcry.add_branch_joint"

    def execute(self, context):
        active_object = context.active_object
        bpy.ops.object.mode_set(mode="OBJECT")
        selected_vert_coordinates = get_vertex_data()
        if selected_vert_coordinates:
            selected_vert = selected_vert_coordinates[0]
            bpy.ops.object.add(
                radius=0.25,
                type="EMPTY",
                enter_editmode=False,
                align="WORLD",
                location=(selected_vert[0], selected_vert[1], selected_vert[2]),
            )
            empty_object = context.active_object
            empty_object.name = name_branch(False)
            utils.set_active(active_object)
            bpy.ops.object.mode_set(mode="EDIT")

            bcPrint("Added new vegetation branch joint helper.")
        return {"FINISHED"}

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "MESH"
            or context.object.mode != "EDIT"
            or not get_vertex_data()
        ):
            self.report({"ERROR"}, "Select a vertex in EDIT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_edit_physic_proxy(bpy.types.Operator):
    """Edit Physic Proxy Properties for selected object."""

    bl_label = "Edit physic proxy properties of active object."
    bl_idname = "bcry.edit_physics_proxy"

    is_proxy: BoolProperty(
        name="Use Physic Proxy",
        description="Enable custom physical proxy primitive variables.",
    )

    info = "Force this proxy to be a {} primitive in the engine."

    proxy_type: EnumProperty(
        name="Physic Proxy",
        items=(
            ("box", "Box", info.format("Box")),
            ("cylinder", "Cylinder", info.format("Cylinder")),
            ("capsule", "Capsule", info.format("Capsule")),
            ("sphere", "Sphere", info.format("Sphere")),
            ("notaprim", "Not a primitive", constants.DESCRIPTIONS["notaprim"]),
        ),
        default="box",
    )

    no_exp_occlusion: BoolProperty(
        name="No Explosion Occlusion",
        description=constants.DESCRIPTIONS["no_exp_occlusion"],
    )
    colltype_player: BoolProperty(
        name="Colltype Player", description=constants.DESCRIPTIONS["colltpye_player"]
    )

    object_ = None

    def invoke(self, context, event):
        self.object_ = context.active_object
        if self.object_ is None or self.object_.type not in ("MESH", "EMPTY"):
            self.report({"ERROR"}, "Please select a valid mesh or Empty helper object.")
            return {"CANCELLED"}

        self.proxy_type, self.is_proxy = udp.get_udp(
            self.object_, "phys_proxy", self.proxy_type, self.is_proxy
        )
        self.no_exp_occlusion = udp.get_udp(
            self.object_, "no_explosion_occlusion", self.no_exp_occlusion
        )
        self.colltype_player = udp.get_udp(
            self.object_, "colltype_player", self.colltype_player
        )

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.object_ is None:
            self.report({"ERROR"}, "No active object selected.")
            return {"CANCELLED"}

        udp.edit_udp(self.object_, "phys_proxy", self.proxy_type, self.is_proxy)
        udp.edit_udp(
            self.object_,
            "no_explosion_occlusion",
            "no_explosion_occlusion",
            self.no_exp_occlusion,
        )
        udp.edit_udp(
            self.object_, "colltype_player", "colltype_player", self.colltype_player
        )
        return {"FINISHED"}


class BCRY_OT_edit_render_mesh(bpy.types.Operator):
    """Edit Render Mesh Properties for selected object."""

    bl_label = "Edit render mesh properties of active object."
    bl_idname = "bcry.edit_render_mesh"

    is_entity: BoolProperty(
        name="Entity", description=constants.DESCRIPTIONS["is_entity"]
    )

    info = "If you want to use {} property. Please enable this."

    is_mass: BoolProperty(name="Use Mass", description=info.format("mass"))
    mass: FloatProperty(name="Mass", description=constants.DESCRIPTIONS["mass"])

    is_density: BoolProperty(name="Use Density", description=info.format("density"))
    density: FloatProperty(
        name="Density", description=constants.DESCRIPTIONS["density"]
    )

    is_pieces: BoolProperty(name="Use Pieces", description=info.format("pieces"))
    pieces: FloatProperty(name="Pieces", description=constants.DESCRIPTIONS["pieces"])

    is_dynamic: BoolProperty(
        name="Dynamic", description=constants.DESCRIPTIONS["is_dynamic"]
    )
    no_hit_refinement: BoolProperty(
        name="No Hit Refinement",
        description=constants.DESCRIPTIONS["no_hit_refinement"],
    )
    other_rendermesh: BoolProperty(
        name="Other Rendermesh", description=constants.DESCRIPTIONS["other_rendermesh"]
    )

    hull: BoolProperty(name="Hull", description="Hull for vehicles.")
    wheel: BoolProperty(name="Wheel", description="Wheel for vehicles.")

    object_ = None

    def execute(self, context):
        if self.object_ is None:
            self.report({"ERROR"}, "No active object selected.")
            return {"CANCELLED"}

        udp.edit_udp(self.object_, "entity", "entity", self.is_entity)
        udp.edit_udp(self.object_, "mass", self.mass, self.is_mass)
        udp.edit_udp(self.object_, "density", self.density, self.is_density)
        udp.edit_udp(self.object_, "pieces", self.pieces, self.is_pieces)
        udp.edit_udp(self.object_, "dynamic", "dynamic", self.is_dynamic)
        udp.edit_udp(
            self.object_,
            "no_hit_refinement",
            "no_hit_refinement",
            self.no_hit_refinement,
        )
        udp.edit_udp(
            self.object_, "other_rendermesh", "other_rendermesh", self.other_rendermesh
        )
        udp.edit_udp(self.object_, "hull", "hull", self.hull)
        udp.edit_udp(self.object_, "wheel", "wheel", self.wheel)

        return {"FINISHED"}

    def invoke(self, context, event):
        self.object_ = context.active_object
        if self.object_ is None or self.object_.type not in ("MESH", "EMPTY"):
            self.report({"ERROR"}, "Please select a valid mesh or Empty helper object.")
            return {"CANCELLED"}

        self.mass, self.is_mass = udp.get_udp(
            self.object_, "mass", self.mass, self.is_mass
        )
        self.density, self.is_density = udp.get_udp(
            self.object_, "density", self.density, self.is_density
        )
        self.pieces, self.is_pieces = udp.get_udp(
            self.object_, "pieces", self.pieces, self.is_pieces
        )
        self.no_hit_refinement = udp.get_udp(
            self.object_, "no_hit_refinement", self.no_hit_refinement
        )
        self.other_rendermesh = udp.get_udp(
            self.object_, "other_rendermesh", self.other_rendermesh
        )

        self.is_entity = udp.get_udp(self.object_, "entity", self.is_entity)
        self.is_dynamic = udp.get_udp(self.object_, "dynamic", self.is_dynamic)

        self.hull = udp.get_udp(self.object_, "hull", self.hull)
        self.wheel = udp.get_udp(self.object_, "wheel", self.wheel)

        return context.window_manager.invoke_props_dialog(self)


class BCRY_OT_edit_joint_node(bpy.types.Operator):
    """Edit Joint Node Properties for selected joint."""

    bl_label = "Edit joint node properties of active object."
    bl_idname = "bcry.edit_joint_node"

    is_limit: BoolProperty(
        name="Use Limit Property",
        description="Configure breakable joint threshold parameters.",
    )
    limit: FloatProperty(name="Limit", description=constants.DESCRIPTIONS["limit"])

    is_bend: BoolProperty(
        name="Use Bend Property", description="Configure joint bend allowances."
    )
    bend: FloatProperty(name="Bend", description=constants.DESCRIPTIONS["bend"])

    is_twist: BoolProperty(
        name="Use Twist Property", description="Configure joint twisting parameters."
    )
    twist: FloatProperty(name="Twist", description=constants.DESCRIPTIONS["twist"])

    is_pull: BoolProperty(
        name="Use Pull Property", description="Configure joint tension pull boundaries."
    )
    pull: FloatProperty(name="Pull", description=constants.DESCRIPTIONS["pull"])

    is_push: BoolProperty(
        name="Use Push Property",
        description="Configure joint compression push properties.",
    )
    push: FloatProperty(name="Push", description=constants.DESCRIPTIONS["push"])

    is_shift: BoolProperty(
        name="Use Shift Property", description="Configure spatial shifting boundaries."
    )
    shift: FloatProperty(name="Shift", description=constants.DESCRIPTIONS["shift"])

    player_can_break: BoolProperty(
        name="Player can break", description=constants.DESCRIPTIONS["player_can_break"]
    )
    gameplay_critical: BoolProperty(
        name="Gameplay critical",
        description=constants.DESCRIPTIONS["gameplay_critical"],
    )

    object_ = None

    def execute(self, context):
        if self.object_ is None:
            self.report({"ERROR"}, "No active object selected.")
            return {"CANCELLED"}

        udp.edit_udp(self.object_, "limit", self.limit, self.is_limit)
        udp.edit_udp(self.object_, "bend", self.bend, self.is_bend)
        udp.edit_udp(self.object_, "twist", self.twist, self.is_twist)
        udp.edit_udp(self.object_, "pull", self.pull, self.is_pull)
        udp.edit_udp(self.object_, "push", self.push, self.is_push)
        udp.edit_udp(self.object_, "shift", self.shift, self.is_shift)
        udp.edit_udp(
            self.object_, "player_can_break", "player_can_break", self.player_can_break
        )
        udp.edit_udp(
            self.object_,
            "gameplay_critical",
            "gameplay_critical",
            self.gameplay_critical,
        )

        return {"FINISHED"}

    def invoke(self, context, event):
        self.object_ = context.active_object
        if self.object_ is None or self.object_.type not in ("MESH", "EMPTY"):
            self.report({"ERROR"}, "Please select a valid mesh or Empty helper object.")
            return {"CANCELLED"}

        self.limit, self.is_limit = udp.get_udp(
            self.object_, "limit", self.limit, self.is_limit
        )
        self.bend, self.is_bend = udp.get_udp(
            self.object_, "bend", self.bend, self.is_bend
        )
        self.twist, self.is_twist = udp.get_udp(
            self.object_, "twist", self.twist, self.is_twist
        )
        self.pull, self.is_pull = udp.get_udp(
            self.object_, "pull", self.pull, self.is_pull
        )
        self.push, self.is_push = udp.get_udp(
            self.object_, "push", self.push, self.is_push
        )
        self.shift, self.is_shift = udp.get_udp(
            self.object_, "shift", self.shift, self.is_shift
        )
        self.player_can_break = udp.get_udp(
            self.object_, "player_can_break", self.player_can_break
        )
        self.gameplay_critical = udp.get_udp(
            self.object_, "gameplay_critical", self.gameplay_critical
        )

        return context.window_manager.invoke_props_dialog(self)


class BCRY_OT_edit_deformable(bpy.types.Operator):
    """Edit Deformable Properties for selected skeleton mesh."""

    bl_label = "Edit deformable properties of active skeleton mesh."
    bl_idname = "bcry.edit_deformable"

    is_stiffness: BoolProperty(
        name="Use Stiffness",
        description="Enable physical joint stiffness modifications.",
    )
    stiffness: FloatProperty(
        name="Stiffness", description=constants.DESCRIPTIONS["stiffness"], default=10.0
    )

    is_hardness: BoolProperty(
        name="Use Hardness", description="Enable physical joint hardness modifications."
    )
    hardness: FloatProperty(
        name="Hardness", description=constants.DESCRIPTIONS["hardness"], default=10.0
    )

    is_max_stretch: BoolProperty(
        name="Use Max Stretch",
        description="Enable absolute stretch limits on deform elements.",
    )
    max_stretch: FloatProperty(
        name="Max Stretch",
        description=constants.DESCRIPTIONS["max_stretch"],
        default=0.01,
    )

    is_max_impulse: BoolProperty(
        name="Use Max Impulse",
        description="Enable absolute limit on force/impulse tolerances.",
    )
    max_impulse: FloatProperty(
        name="Max Impulse", description=constants.DESCRIPTIONS["max_impulse"]
    )

    is_skin_dist: BoolProperty(
        name="Use Skin Dist", description="Enable custom skinning bounds for joints."
    )
    skin_dist: FloatProperty(
        name="Skin Dist", description=constants.DESCRIPTIONS["skin_dist"]
    )

    is_thickness: BoolProperty(
        name="Use Thickness", description="Enable custom collision boundary scaling."
    )
    thickness: FloatProperty(
        name="Thickness", description=constants.DESCRIPTIONS["thickness"]
    )

    is_explosion_scale: BoolProperty(
        name="Use Explosion Scale",
        description="Scale the impact of explosion forces on soft bodies.",
    )
    explosion_scale: FloatProperty(
        name="Explosion Scale", description=constants.DESCRIPTIONS["explosion_scale"]
    )

    notaprim: BoolProperty(
        name="Is not a primitive", description=constants.DESCRIPTIONS["notaprim"]
    )

    object_ = None

    def invoke(self, context, event):
        self.object_ = context.active_object
        if self.object_ is None or self.object_.type not in ("MESH", "EMPTY"):
            self.report({"ERROR"}, "Please select a valid mesh or Empty helper object.")
            return {"CANCELLED"}

        self.stiffness, self.is_stiffness = udp.get_udp(
            self.object_, "stiffness", self.stiffness, self.is_stiffness
        )
        self.hardness, self.is_hardness = udp.get_udp(
            self.object_, "hardness", self.hardness, self.is_hardness
        )
        self.max_stretch, self.is_max_stretch = udp.get_udp(
            self.object_, "max_stretch", self.max_stretch, self.is_max_stretch
        )
        self.max_impulse, self.is_max_impulse = udp.get_udp(
            self.object_, "max_impulse", self.max_impulse, self.is_max_impulse
        )
        self.skin_dist, self.is_skin_dist = udp.get_udp(
            self.object_, "skin_dist", self.skin_dist, self.is_skin_dist
        )
        self.thickness, self.is_thickness = udp.get_udp(
            self.object_, "thickness", self.thickness, self.is_thickness
        )
        self.explosion_scale, self.is_explosion_scale = udp.get_udp(
            self.object_,
            "explosion_scale",
            self.explosion_scale,
            self.is_explosion_scale,
        )
        self.notaprim = udp.get_udp(self.object_, "notaprim", self.notaprim)

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.object_ is None:
            self.report({"ERROR"}, "No active object selected.")
            return {"CANCELLED"}

        udp.edit_udp(self.object_, "stiffness", self.stiffness, self.is_stiffness)
        udp.edit_udp(self.object_, "hardness", self.hardness, self.is_hardness)
        udp.edit_udp(self.object_, "max_stretch", self.max_stretch, self.is_max_stretch)
        udp.edit_udp(self.object_, "max_impulse", self.max_impulse, self.is_max_impulse)
        udp.edit_udp(self.object_, "skin_dist", self.skin_dist, self.is_skin_dist)
        udp.edit_udp(self.object_, "thickness", self.thickness, self.is_thickness)
        udp.edit_udp(
            self.object_,
            "explosion_scale",
            self.explosion_scale,
            self.is_explosion_scale,
        )
        udp.edit_udp(self.object_, "notaprim", "notaprim", self.notaprim)
        return {"FINISHED"}


class BCRY_OT_fix_wheel_transforms(bpy.types.Operator):
    """Fix vehicle helper transforms to match bound centers."""

    bl_label = "Fix Wheel Transforms"
    bl_idname = "bcry.fix_wheel_transforms"

    def execute(self, context):
        ob = context.active_object
        if ob is None or ob.type != "MESH":
            self.report({"ERROR"}, "Please select a vehicle wheel mesh.")
            return {"CANCELLED"}

        ob.location.x = (ob.bound_box[0][0] + ob.bound_box[1][0]) / 2.0
        ob.location.y = (ob.bound_box[2][0] + ob.bound_box[3][0]) / 2.0
        ob.location.z = (ob.bound_box[4][0] + ob.bound_box[5][0]) / 2.0
        return {"FINISHED"}


# Expose classes to operators/__init__.py dynamically
classes = (
    BCRY_OT_add_proxy,
    BCRY_OT_add_mesh_proxy,
    BCRY_OT_add_breakable_joint,
    BCRY_OT_add_branch,
    BCRY_OT_add_branch_joint,
    BCRY_OT_edit_physic_proxy,
    BCRY_OT_edit_render_mesh,
    BCRY_OT_edit_joint_node,
    BCRY_OT_edit_deformable,
    BCRY_OT_fix_wheel_transforms,
)
