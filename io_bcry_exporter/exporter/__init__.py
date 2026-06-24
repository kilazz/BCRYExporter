# ------------------------------------------------------------------------------
# Name:        exporter/__init__.py
# Purpose:     Initialization and reload management for the COLLADA exporters
# ------------------------------------------------------------------------------

if "bpy" in locals():
    import importlib

    # Explicitly import submodules into current namespace before reloading to prevent NameError on script reloads
    from . import dae_base, dae_geometry, dae_animation, materials

    importlib.reload(dae_base)
    importlib.reload(dae_geometry)
    importlib.reload(dae_animation)
    importlib.reload(materials)
else:
    import bpy  # noqa: F401
    from . import dae_base, dae_geometry, dae_animation, materials


def register():
    """No Blender class registration needed for core DAE exporter modules."""
    pass


def unregister():
    """No Blender class unregistration needed for core DAE exporter modules."""
    pass
