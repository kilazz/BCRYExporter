# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
#
# ------------------------------------------------------------------------------
# Name:        __init__.py
# Purpose:     Primary entry point for BCRY Exporter add-on (Modular Architecture)
#
# Author:      Özkan Afacan, Angelo J. Miner, Mikołaj Milej, Daniel White,
#              Oscar Martin Garcia, David Marcelis, Duo Oratar, Zach Wang
#
# License:     GPLv2+
# ------------------------------------------------------------------------------

bl_info = {
    "name": "BCRY Exporter",
    "author": "Özkan Afacan; Angelo J. Miner; Mikołaj Milej; Daniel White; Oscar Martin Garcia; Duo Oratar; David Marcelis; Leonid Bilousov; Zach Wang",
    "blender": (4, 5, 3),
    "version": (1, 3, 0),
    "location": "View3D > Sidebar > BCry Exporter",
    "description": "Export assets from Blender to CryEngine V & Lumberyard",
    "warning": "",
    "wiki_url": "http://bcry.afcstudio.org/documents/",
    "tracker_url": "https://github.com/brickengineer/BCRYExporter/issues",
    "support": "OFFICIAL",
    "category": "Import-Export",
}

# ------------------------------------------------------------------------------
# Module Registration & Reloading System
# ------------------------------------------------------------------------------
# This setup safely handles Blender's "Reload Scripts" (F8) functionality.
# It ensures that all sub-packages are reloaded so you don't have to restart
# Blender every time you make a change to the code.

if "bpy" in locals():
    import importlib

    # Explicitly import modules before reloading them to prevent NameError
    from . import core, utils, engine, exporter, operators, ui

    importlib.reload(core)
    importlib.reload(utils)
    importlib.reload(engine)
    importlib.reload(exporter)
    importlib.reload(operators)
    importlib.reload(ui)
else:
    import bpy  # noqa: F401

    # Initial import of our modular packages
    from . import core, utils, engine, exporter, operators, ui

# Order matters! Core and Utils must be registered before Operators and UI.
# E.g., UI panels depend on Scene properties registered in Core/Operators.
modules = (
    core,
    utils,
    engine,
    exporter,
    operators,
    ui,
)


def register():
    """Register all modules and classes with Blender."""
    for module in modules:
        # Delegate registration to the __init__.py of each sub-folder
        if hasattr(module, "register"):
            module.register()


def unregister():
    """Unregister all modules and classes from Blender."""
    # Unregister in reverse order to cleanly resolve dependencies
    for module in reversed(modules):
        if hasattr(module, "unregister"):
            module.unregister()


if __name__ == "__main__":
    register()
