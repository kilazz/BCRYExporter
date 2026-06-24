# ruff: noqa: F403, F405
# ------------------------------------------------------------------------------
# Name:        utils/__init__.py
# Purpose:     Unified package interface for BCRY Exporter utilities
# ------------------------------------------------------------------------------

# Handle reloading when pressing F8 in Blender to update modified submodules
if "bpy" in locals():
    import importlib

    # Explicitly import submodules into current namespace before reloading to prevent NameError on script reloads
    from . import math, paths, mesh, armature, export_node

    importlib.reload(math)
    importlib.reload(paths)
    importlib.reload(mesh)
    importlib.reload(armature)
    importlib.reload(export_node)
else:
    # Initial import of our split utility modules
    from . import math, paths, mesh, armature, export_node

# Expose all utility functions at the 'utils' package namespace level.
# This prevents breaking imports in existing exporter and operator code.
from .math import *
from .paths import *
from .mesh import *
from .armature import *
from .export_node import *


def register():
    """No Blender class registration needed for pure Python helper utilities."""
    pass


def unregister():
    """No Blender class unregistration needed for pure Python helper utilities."""
    pass
