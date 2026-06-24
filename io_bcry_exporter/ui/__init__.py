# ------------------------------------------------------------------------------
# Name:        ui/__init__.py
# Purpose:     Initialization and registration of UI elements (Panels & Menus)
# ------------------------------------------------------------------------------

import bpy

if "bpy" in locals():
    import importlib

    # Explicitly import submodules into current namespace before reloading to prevent NameError on script reloads
    from . import panels, menus

    importlib.reload(panels)
    importlib.reload(menus)
else:
    from . import panels, menus


# Group all UI classes that need registration.
# The order here defines how they appear in the UI registration queue,
# though the layout order in the N-panel is controlled by Blender internally.
classes = (
    panels.BCRY_PT_export_utilities_panel,
    panels.BCRY_PT_cry_utilities_panel,
    panels.BCRY_PT_bone_utilities_panel,
    panels.BCRY_PT_mesh_utilities_panel,
    panels.BCRY_PT_material_utilities_panel,
    panels.BCRY_PT_user_defined_properties_panel,
    panels.BCRY_PT_configurations_panel,
    panels.BCRY_PT_export_panel,
    menus.BCRY_MT_set_material_physics_menu,
)

# ------------------------------------------------------------------------------
# Native Menu Injections
# ------------------------------------------------------------------------------
# These callbacks are used to inject our custom tools directly into Blender's
# native right-click and dropdown menus.


def draw_physics_menu(self, context):
    """Appends the BCRY Physical Material menu to Blender's native Material context menu."""
    layout = self.layout
    layout.separator()
    layout.label(text="BCry Exporter")
    layout.menu(menus.BCRY_MT_set_material_physics_menu.bl_idname, icon="PHYSICS")


def draw_remove_unused_vertex_groups(self, context):
    """Appends the BCRY vertex group cleanup tool to Blender's native Vertex Group dropdown."""
    layout = self.layout
    layout.separator()
    layout.label(text="BCry Exporter")

    # We call the operator by its bl_idname.
    # The actual operator class lives in `operators/mesh_ops.py`.
    layout.operator("bcry.remove_unused_vertex_groups", icon="X")


# ------------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------------


def register():
    """Register UI classes and append injections to native menus."""
    for cls in classes:
        bpy.utils.register_class(cls)

    # Inject into Blender's native UI
    bpy.types.MATERIAL_MT_context_menu.append(draw_physics_menu)
    bpy.types.MESH_MT_vertex_group_context_menu.append(draw_remove_unused_vertex_groups)


def unregister():
    """Unregister UI classes and remove injections from native menus."""
    # Remove from Blender's native UI
    bpy.types.MATERIAL_MT_context_menu.remove(draw_physics_menu)
    bpy.types.MESH_MT_vertex_group_context_menu.remove(draw_remove_unused_vertex_groups)

    # Unregister custom classes in reverse order
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
