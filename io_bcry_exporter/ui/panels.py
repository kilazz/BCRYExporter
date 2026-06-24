# ------------------------------------------------------------------------------
# Name:        ui/panels.py
# Purpose:     All N-panel (sidebar) classes for the 3D Viewport
# ------------------------------------------------------------------------------

import bpy

# Import the core module to access our custom icons dictionary later
from .. import core


class View3DPanel:
    """Base class for all BCRY Exporter panels."""

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BCry Exporter"
    bl_options = {"DEFAULT_CLOSED"}


class BCRY_PT_export_utilities_panel(View3DPanel, bpy.types.Panel):
    bl_label = "Export Utilities"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("bcry.add_cry_export_node", text="Add Export Node", icon="GROUP")
        row = col.row(align=True)
        row.operator(
            "bcry.selected_to_cry_export_nodes",
            text="Export Nodes from Objects",
            icon="SCENE_DATA",
        )

        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator(
            "bcry.add_cry_animation_node",
            text="Add Animation Node",
            icon="PREVIEW_RANGE",
        )

        col.separator()
        col.operator(
            "bcry.apply_transforms",
            text="Apply All Transforms",
            icon="MESH_DATA",
        )
        col.operator("bcry.feet_on_floor", text="Feet On Floor", icon="ARMATURE_DATA")


class BCRY_PT_cry_utilities_panel(View3DPanel, bpy.types.Panel):
    bl_label = "Cry Utilities"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        # Access the property group registered in core/properties.py
        proxy_props = context.scene.proxy_props

        # Predefine variables for props
        if proxy_props.bAdvanced:
            bChild = proxy_props.bChild
            bSeparate = proxy_props.bSeparate
        else:
            bChild = False
            bSeparate = False

        col.label(text="Add Physics Proxy", icon="PHYSICS")
        col.separator()
        row = col.row(align=True)

        add_box_proxy = row.operator("bcry.add_proxy", text="Box", icon="META_CUBE")
        add_box_proxy.type_ = "box"
        add_box_proxy.child_ = bChild

        add_capsule_proxy = row.operator(
            "bcry.add_proxy", text="Capsule", icon="META_CAPSULE"
        )
        add_capsule_proxy.type_ = "capsule"
        add_capsule_proxy.child_ = bChild

        row = col.row(align=True)
        add_cylinder_proxy = row.operator(
            "bcry.add_proxy", text="Cylinder", icon="META_ELLIPSOID"
        )
        add_cylinder_proxy.type_ = "cylinder"
        add_cylinder_proxy.child_ = bChild

        add_sphere_proxy = row.operator(
            "bcry.add_proxy", text="Sphere", icon="META_BALL"
        )
        add_sphere_proxy.type_ = "sphere"
        add_sphere_proxy.child_ = bChild

        row = col.row(align=True)
        add_mesh_proxy = row.operator(
            "bcry.add_mesh_proxy", text="Mesh", icon="META_ELLIPSOID"
        )
        add_mesh_proxy.child_ = bChild
        add_mesh_proxy.separate_ = bSeparate

        row = col.row()
        row.separator()

        if proxy_props.bAdvanced:
            icon = "UNLOCKED"
        else:
            icon = "LOCKED"

        row = col.row()
        row.prop(proxy_props, "bAdvanced", toggle=True, icon=icon)

        if proxy_props.bAdvanced:
            row = col.row()
            row.prop(proxy_props, "bChild")
            row = col.row()
            if context.mode == "OBJECT":
                row.prop(proxy_props, "bSeparate")

        col.separator()
        col.separator()

        col.operator("bcry.add_breakable_joint", text="Add Joint", icon="PARTICLES")

        col.separator()
        col.separator()

        col.operator("bcry.add_branch", text="Add Branch", icon="MOD_SIMPLEDEFORM")
        col.operator(
            "bcry.add_branch_joint",
            text="Add Branch Joint",
            icon="MOD_SIMPLEDEFORM",
        )


class BCRY_PT_bone_utilities_panel(View3DPanel, bpy.types.Panel):
    bl_label = "Bone Utilities"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.operator("bcry.add_root_bone", text="Add Root Bone", icon="BONE_DATA")
        col.operator(
            "bcry.add_primitive_mesh",
            text="Add Primitive Mesh",
            icon="BONE_DATA",
        )
        col.operator(
            "bcry.add_locator_locomotion",
            text="Add Locator Locomotion",
            icon="BONE_DATA",
        )

        col.separator()

        col.operator(
            "bcry.edit_inverse_kinematics",
            text="Edit Bone Physic and IKs",
            icon="OUTLINER_DATA_ARMATURE",
        )
        col.operator(
            "bcry.apply_animation_scaling",
            text="Apply Animation Scaling",
            icon="OUTLINER_DATA_ARMATURE",
        )

        col.separator()

        col.operator(
            "bcry.physicalize_skeleton",
            text="Physicalize Skeleton",
            icon="PHYSICS",
        )
        col.operator(
            "bcry.clear_skeleton_physics",
            text="Clear Skeleton Physics",
            icon="PHYSICS",
        )

        col = layout.column(align=True)
        row = col.row(align=True)
        row = col.row()
        row.label(text="Experimental:")

        row = col.row()
        row.operator(
            "bcry.fix_bone_orientations",
            text="Fix Bone Orientations",
            icon="CON_KINEMATIC",
        )

        row = col.row()
        row.operator(
            "bcry.rebuild_armature",
            text="Rebuild armature",
            icon="OUTLINER_DATA_ARMATURE",
        )


class BCRY_PT_mesh_utilities_panel(View3DPanel, bpy.types.Panel):
    bl_label = "Mesh Utilities"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.operator(
            "bcry.generate_lod_meshes",
            text="Generate LODs",
            icon="MOD_EXPLODE",
        )
        col.separator()

        col.separator()
        col.operator("bcry.find_weightless", text="Find Weightless", icon="WPAINT_HLT")
        col.operator("bcry.remove_weight", text="Remove Weight", icon="WPAINT_HLT")

        col.separator()

        col.operator(
            "bcry.find_degenerate_faces",
            text="Find Degenerate",
            icon="ZOOM_ALL",
        )
        col.operator(
            "bcry.find_multiface_lines",
            text="Find Multi-face",
            icon="ZOOM_ALL",
        )

        col.separator()

        col.operator(
            "bcry.find_no_uvs",
            text="Find All Objects with No UV's",
            icon="UV_FACESEL",
        )
        col.operator(
            "bcry.add_uv_texture",
            text="Add UV's to Objects",
            icon="UV_FACESEL",
        )

        col.separator()
        col.label(text="Cry Decal & Flow Tools:", icon="BRUSH_DATA")
        col.operator(
            "bcry.create_decal", text="Create Decal (Project)", icon="MOD_SHRINKWRAP"
        )
        col.operator("bcry.flow_paint", text="Flow Paint Tool", icon="BRUSH_DATA")


class BCRY_PT_material_utilities_panel(View3DPanel, bpy.types.Panel):
    bl_label = "Material Utilities"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.operator(
            "bcry.add_cry_material",
            text="Add Material to Selected Objects",
            icon="VIEWZOOM",
        )
        col.separator()
        col.operator(
            "bcry.add_material_properties",
            text="Add Material Properties",
            icon="GREASEPENCIL",
        )
        col.operator(
            "bcry.discard_material_properties",
            text="Discard Material Properties",
            icon="BRUSH_DATA",
        )
        col.separator()
        col.operator(
            "bcry.generate_materials",
            text="Generate Node Materials",
            icon="GROUP_VCOL",
        )


class BCRY_PT_user_defined_properties_panel(View3DPanel, bpy.types.Panel):
    bl_label = "User Defined Properties"

    def draw(self, layout_context):
        layout = self.layout
        col = layout.column(align=True)

        col.operator(
            "bcry.edit_render_mesh",
            text="Edit Render Mesh",
            icon="FORCE_LENNARDJONES",
        )
        col.operator(
            "bcry.edit_physics_proxy",
            text="Edit Physic Proxy",
            icon="META_CUBE",
        )
        col.operator("bcry.edit_joint_node", text="Edit Joint", icon="MOD_SCREW")
        col.operator(
            "bcry.edit_deformable",
            text="Edit Deformable",
            icon="MOD_SIMPLEDEFORM",
        )


class BCRY_PT_configurations_panel(View3DPanel, bpy.types.Panel):
    bl_label = "Configurations"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.operator("bcry.find_rc", text="Find RC", icon="SCRIPTPLUGINS")
        col.operator(
            "bcry.find_rc_for_texture_conversion",
            text="Find Texture RC",
            icon="SCRIPTPLUGINS",
        )
        col.separator()
        col.operator(
            "bcry.select_game_dir",
            text="Select Game Directory",
            icon="FILEBROWSER",
        )
        col.separator()


class BCRY_PT_export_panel(View3DPanel, bpy.types.Panel):
    bl_label = "Export"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.operator(
            "bcry.export_animations",
            text="Export Animations",
            icon="RENDER_ANIMATION",
        )
        col.separator()

        # Access the global custom icon from our core module with a safe fallback
        icon_id = "QUESTION"
        if "main" in core.icons.preview_collections:
            pcoll = core.icons.preview_collections["main"]
            if "crye" in pcoll:
                icon_id = pcoll["crye"].icon_id

        # Safely assign icons depending on whether custom texture was loaded
        if isinstance(icon_id, int):
            col.operator(
                "bcry.export_to_game_quick",
                text="Quick Export",
                icon_value=icon_id,
            )
            col.operator(
                "bcry.export_to_game",
                text="Export to CryEngine",
                icon_value=icon_id,
            )
        else:
            col.operator(
                "bcry.export_to_game_quick",
                text="Quick Export",
                icon=icon_id,
            )
            col.operator(
                "bcry.export_to_game",
                text="Export to CryEngine",
                icon=icon_id,
            )
        col.separator()
