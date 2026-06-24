# ------------------------------------------------------------------------------
# Name:        ui/menus.py
# Purpose:     Custom dropdown menus and context menus for the UI
# ------------------------------------------------------------------------------

import bpy


class BCRY_MT_set_material_physics_menu(bpy.types.Menu):
    """Dropdown menu for quickly assigning physical properties to materials."""

    bl_label = "Set Physical Material"
    bl_idname = "BCRY_MT_set_material_physics"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Set Material Physics")
        layout.separator()

        # We use the bl_idname of the operators as strings to avoid circular imports.
        # These operators will be defined in operators/material.py

        layout.operator(
            "bcry.set_phys_default",
            text="physDefault",
            icon="PHYSICS",
        )
        layout.operator(
            "bcry.set_phys_proxy_no_draw",
            text="physProxyNoDraw",
            icon="PHYSICS",
        )
        layout.operator(
            "bcry.set_phys_none",
            text="physNone",
            icon="PHYSICS",
        )
        layout.operator(
            "bcry.set_phys_obstruct",
            text="physObstruct",
            icon="PHYSICS",
        )
        layout.operator(
            "bcry.set_phys_no_collide",
            text="physNoCollide",
            icon="PHYSICS",
        )
