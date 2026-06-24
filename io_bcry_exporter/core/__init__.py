# ------------------------------------------------------------------------------
# Name:        core/__init__.py
# Purpose:     Initialization of core systems (Icons, Properties, Config, Logger)
# ------------------------------------------------------------------------------

if "bpy" in locals():
    import importlib

    # Explicitly import submodules into current namespace before reloading to prevent NameError on script reloads
    from . import icons, properties, config, logger, exceptions

    importlib.reload(icons)
    importlib.reload(properties)
    importlib.reload(config)
    importlib.reload(logger)
    importlib.reload(exceptions)
else:
    import bpy  # noqa: F401
    from . import icons, properties, config, logger, exceptions


def register():
    """Register core systems with Blender."""
    icons.register()
    properties.register()


def unregister():
    """Unregister core systems from Blender."""
    properties.unregister()
    icons.unregister()
