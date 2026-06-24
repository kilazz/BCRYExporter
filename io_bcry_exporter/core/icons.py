# ------------------------------------------------------------------------------
# Name:        core/icons.py
# Purpose:     Loads and caches custom icons for the Blender UI
# ------------------------------------------------------------------------------

import os
import bpy.utils.previews

# A dictionary to safely store our custom icon collections
preview_collections = {}


def register():
    """Load custom icons into memory and store them in the collection."""
    # Prevent double registration during script reload
    if "main" in preview_collections:
        return

    pcoll = bpy.utils.previews.new()

    # Resolve the path to the 'icons' folder
    # __file__ is core/icons.py, so we go up one level to the root addon folder
    core_dir = os.path.dirname(__file__)
    addon_dir = os.path.dirname(core_dir)
    icons_dir = os.path.join(addon_dir, "icons")

    icon_path = os.path.join(icons_dir, "CryEngine.png")

    # Load the icon if it exists to avoid silent crashes
    if os.path.exists(icon_path):
        pcoll.load("crye", icon_path, "IMAGE")
    else:
        print(f"[BCry Exporter Warning] Custom icon not found: {icon_path}")

    preview_collections["main"] = pcoll


def unregister():
    """Remove custom icons from memory."""
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)

    preview_collections.clear()
