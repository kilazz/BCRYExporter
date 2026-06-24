# ------------------------------------------------------------------------------
# Name:        engine/__init__.py
# Purpose:     Initialization and reload management for engine integration submodules
# ------------------------------------------------------------------------------

if "bpy" in locals():
    import importlib

    # Explicitly import submodules into current namespace before reloading to prevent NameError on script reloads
    from . import compiler, udp, constants

    importlib.reload(compiler)
    importlib.reload(udp)
    importlib.reload(constants)
else:
    import bpy  # noqa: F401
    from . import compiler, udp, constants


def register():
    """No Blender class registration needed for core engine utility modules."""
    pass


def unregister():
    """No Blender class unregistration needed for core engine utility modules."""
    pass
