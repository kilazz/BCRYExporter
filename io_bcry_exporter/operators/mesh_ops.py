# ------------------------------------------------------------------------------
# Name:        operators/mesh_ops.py
# Purpose:     All operator classes related to geometry and mesh edits/fixes
# ------------------------------------------------------------------------------

import math
import bpy
import mathutils
from bpy.props import BoolProperty, FloatProperty, IntProperty

# Modular package imports
from ..core.logger import bcPrint
from .. import utils


class BCRY_OT_apply_transforms(bpy.types.Operator):
    """Click to apply transforms on selected objects."""

    bl_label = "Apply Transforms"
    bl_idname = "bcry.apply_transforms"
    bl_options = {"REGISTER", "UNDO"}

    loc: BoolProperty(name="Location", default=False)
    rot: BoolProperty(name="Rotation", default=True)
    scale: BoolProperty(name="Scale", default=True)

    def execute(self, context):
        selected = context.selected_objects
        if selected:
            message = "Applying object transforms."
            bpy.ops.object.transform_apply(
                location=self.loc, rotation=self.rot, scale=self.scale
            )
        else:
            message = "No Object Selected."
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, event):
        if len(context.selected_objects) == 0:
            self.report({"ERROR"}, "Select one or more objects in OBJECT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_feet_on_floor(bpy.types.Operator):
    """Places mesh on grid floor."""

    bl_label = "Feet on Floor"
    bl_idname = "bcry.feet_on_floor"
    bl_options = {"REGISTER", "UNDO"}

    z_offset: FloatProperty(
        name="Z Offset",
        default=0.0,
        step=0.1,
        precision=3,
        description="Z offset for center of object.",
    )

    def execute(self, context):
        old_cursor = context.scene.cursor.location.copy()
        for obj in context.selected_objects:
            ctx = utils.override(obj, active=True, selected=True)
            # Uses standard context.temp_override context manager for Blender 4.x
            with context.temp_override(**ctx):
                bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
                bpy.ops.view3d.snap_cursor_to_selected()
                x, y, z = context.scene.cursor.location
                z = obj.location.z - obj.dimensions.z / 2 - self.z_offset
                context.scene.cursor.location = mathutils.Vector((x, y, z))
                bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
                context.scene.cursor.location = mathutils.Vector((0, 0, 0))
                bpy.ops.view3d.snap_selected_to_cursor()

        context.scene.cursor.location = old_cursor
        return {"FINISHED"}

    def invoke(self, context, event):
        if not context.selected_objects or context.mode != "OBJECT":
            self.report({"ERROR"}, "Select one or more objects in OBJECT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_generate_lods(bpy.types.Operator):
    """Generate LOD meshes for selected object."""

    bl_label = "Generate LOD Meshes"
    bl_idname = "bcry.generate_lod_meshes"
    bl_options = {"REGISTER", "UNDO"}

    lod_count: IntProperty(
        name="LOD Count",
        default=2,
        min=1,
        max=5,
        step=1,
        description="LOD count to generate.",
    )

    decimate_ratio: FloatProperty(
        name="Decimate Ratio",
        default=0.5,
        min=0.001,
        max=1.000,
        precision=3,
        step=0.1,
        description="Decimate ratio for LODs.",
    )

    view_offset: FloatProperty(
        name="View Offset",
        default=1.5,
        precision=3,
        description="View offset in scene.",
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "lod_count")
        col.prop(self, "decimate_ratio")
        col = layout.column()
        col.prop(self, "view_offset")
        col.separator()

    def execute(self, context):
        object_ = context.active_object

        for obj in context.scene.objects:
            if object_.name != obj.name:
                obj.select_set(False)

        ALLOWED_NODE_TYPES = ("cgf", "cga", "skin")
        for collection in object_.users_collection:
            if utils.is_export_node(collection):
                node_type = utils.get_node_type(collection)
                if node_type in ALLOWED_NODE_TYPES:
                    break

        bpy.ops.object.duplicate()
        lod = context.active_object
        lod.location.x += self.view_offset

        bpy.ops.object.modifier_add(type="DECIMATE")
        decimate = lod.modifiers[len(lod.modifiers) - 1]
        decimate.ratio = self.decimate_ratio

        lod_name = f"{object_.name}_LOD1"
        lod.name = lod_name
        lod.data.name = lod_name

        for index in range(2, self.lod_count + 1):
            bpy.ops.object.duplicate()

            lod = context.active_object
            lod.location.x += self.view_offset
            decimate = lod.modifiers[len(lod.modifiers) - 1]
            decimate.ratio = self.decimate_ratio / math.pow(2, index)

            lod_name = f"{object_.name}_LOD{index}"
            lod.name = lod_name
            lod.data.name = lod_name

        return {"FINISHED"}

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "MESH"
            or context.object.mode != "OBJECT"
        ):
            self.report({"ERROR"}, "Select a mesh in OBJECT mode.")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self)


class BCRY_OT_find_degenerate_faces(bpy.types.Operator):
    """Select the object to test in object mode with nothing selected in \
    it's mesh before running this."""

    bl_label = "Find Degenerate Faces"
    bl_idname = "bcry.find_degenerate_faces"

    area_epsilon = 0.000001

    def execute(self, context):
        saved_mode = context.object.mode
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")

        bpy.ops.object.mode_set(mode="OBJECT")
        mesh = context.active_object.data

        vert_list = [vert for vert in mesh.vertices]
        context.tool_settings.mesh_select_mode = (True, False, False)
        bcPrint("Locating degenerate faces.")
        degenerate_count = 0

        for poly in mesh.polygons:
            if poly.area < self.area_epsilon:
                bcPrint("Found a degenerate face.")
                degenerate_count += 1
                for v in poly.vertices:
                    bcPrint("Selecting face vertices.")
                    vert_list[v].select = True

        if degenerate_count > 0:
            bpy.ops.object.mode_set(mode="EDIT")
            self.report({"WARNING"}, f"Found {degenerate_count} degenerate faces")
        else:
            self.report({"INFO"}, "No degenerate faces found")
            bpy.ops.object.mode_set(mode=saved_mode)

        return {"FINISHED"}

    def invoke(self, context, event):
        if context.object is None or context.object.type != "MESH":
            self.report({"ERROR"}, "Select a mesh in OBJECT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_find_multiface_lines(bpy.types.Operator):
    """Select the object to test in object mode with nothing selected in \
    it's mesh before running this."""

    bl_label = "Find Lines with 3+ Faces."
    bl_idname = "bcry.find_multiface_lines"

    def execute(self, context):
        mesh = context.active_object.data
        vert_list = [vert for vert in mesh.vertices]
        context.tool_settings.mesh_select_mode = (True, False, False)
        bpy.ops.object.mode_set(mode="OBJECT")
        bcPrint("Locating degenerate faces.")
        for i in mesh.edges:
            counter = 0
            for polygon in mesh.polygons:
                if (
                    i.vertices[0] in polygon.vertices
                    and i.vertices[1] in polygon.vertices
                ):
                    counter += 1
            if counter > 2:
                bcPrint("Found a multi-face line")
                for v in i.vertices:
                    bcPrint("Selecting line vertices.")
                    vert_list[v].select = True
        bpy.ops.object.mode_set(mode="EDIT")
        return {"FINISHED"}

    def invoke(self, context, event):
        if context.object is None or context.object.type != "MESH":
            self.report({"ERROR"}, "Select a mesh in OBJECT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_find_weightless(bpy.types.Operator):
    """Finds out unassigned vertices to any bone."""

    bl_label = "Find Weightless Vertices"
    bl_idname = "bcry.find_weightless"

    weight_epsilon = 0.0001
    message = ""
    vert_count = 0

    def execute(self, context):
        self.vert_count = 0

        if context.active_object is None or context.active_object.type != "MESH":
            self.report({"ERROR"}, "Please select a mesh in OBJECT mode.")
            return None

        object_ = context.active_object
        if object_.parent is None or object_.parent.type != "ARMATURE":
            self.report({"ERROR"}, "Please select a mesh in OBJECT mode.")
            return None

        armature = object_.parent

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        if object_.type == "MESH":
            for v in object_.data.vertices:
                if not v.groups:
                    v.select = True
                    self.vert_count += 1
                else:
                    weight = 0
                    for g in v.groups:
                        group_name = object_.vertex_groups[g.group].name
                        if group_name in armature.pose.bones:
                            weight += g.weight
                    if weight < self.weight_epsilon:
                        v.select = True
                        self.vert_count += 1
        object_.data.update()

        if self.vert_count == 0:
            self.message = "Selected mesh has no weightless vertices."
        else:
            self.message = f"Selected mesh has {self.vert_count} weightless vertices."
        return {"FINISHED"}

    def invoke(self, context, event):
        if context.object is None or context.object.type != "MESH":
            self.report({"ERROR"}, "Please select a mesh in OBJECT mode.")
            return {"FINISHED"}
        object_ = context.object
        if object_.parent is None or object_.parent.type != "ARMATURE":
            self.report({"ERROR"}, "Please select a mesh in OBJECT mode.")
            return {"FINISHED"}

        return context.window_manager.invoke_props_dialog(self)


class BCRY_OT_remove_all_weight(bpy.types.Operator):
    """Clear all weight information from selected mesh."""

    bl_label = "Remove All Weight from Selected Vertices"
    bl_idname = "bcry.remove_weight"

    def execute(self, context):
        object_ = context.active_object
        if object_.type == "MESH":
            verts = []
            for v in object_.data.vertices:
                if v.select:
                    verts.append(v)
            for v in verts:
                for g in v.groups:
                    g.weight = 0
        return {"FINISHED"}

    def invoke(self, context, event):
        if (
            context.object is None
            or context.object.type != "MESH"
            or context.object.mode != "EDIT"
        ):
            self.report({"ERROR"}, "Select one or more vertices in EDIT mode.")
            return {"FINISHED"}

        return self.execute(context)


class BCRY_OT_find_no_uvs(bpy.types.Operator):
    """Find objects have no any UV."""

    bl_label = "Find All Objects with No UV's"
    bl_idname = "bcry.find_no_uvs"

    def execute(self, context):
        for object_ in bpy.data.objects:
            object_.select_set(False)

        for object_ in context.selectable_objects:
            if object_.type == "MESH" and not object_.data.uv_layers:
                object_.select_set(True)

        return {"FINISHED"}


class BCRY_OT_add_uv_texture(bpy.types.Operator):
    """Add UVs to all meshes without UVs."""

    bl_label = "Add UV's to Objects"
    bl_idname = "bcry.add_uv_texture"

    def execute(self, context):
        for object_ in bpy.data.objects:
            if object_.type == "MESH":
                uv = False
                for _ in object_.data.uv_layers:
                    uv = True
                    break
                if not uv:
                    utils.set_active(object_)
                    # Uses standard uv_layers.new() as uv_texture_add() is removed in Blender 2.8+
                    object_.data.uv_layers.new()
                    message = f"Added UV map to {object_.name}"
                    self.report({"INFO"}, message)
                    bcPrint(message)

        return {"FINISHED"}


class BCRY_OT_remove_unused_vertex_groups(bpy.types.Operator):
    """Remove vertex groups that have no weights assigned on any vertices."""

    bl_label = "Remove Unused Vertex Groups"
    bl_idname = "bcry.remove_unused_vertex_groups"

    def execute(self, context):
        old_mode = bpy.context.mode
        if old_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        object_ = bpy.context.active_object
        used_indices = []

        for vertex in object_.data.vertices:
            for group in vertex.groups:
                index = group.group
                if index not in used_indices:
                    used_indices.append(index)

        used_vertex_groups = []
        for index in used_indices:
            used_vertex_groups.append(object_.vertex_groups[index])

        for vertex_group in list(object_.vertex_groups):
            if vertex_group not in used_vertex_groups:
                object_.vertex_groups.remove(vertex_group)

        if old_mode != "OBJECT":
            bpy.ops.object.mode_set(mode=old_mode)

        return {"FINISHED"}


# Expose classes to operators/__init__.py dynamically
classes = (
    BCRY_OT_apply_transforms,
    BCRY_OT_feet_on_floor,
    BCRY_OT_generate_lods,
    BCRY_OT_find_degenerate_faces,
    BCRY_OT_find_multiface_lines,
    BCRY_OT_find_weightless,
    BCRY_OT_remove_all_weight,
    BCRY_OT_find_no_uvs,
    BCRY_OT_add_uv_texture,
    BCRY_OT_remove_unused_vertex_groups,
)
