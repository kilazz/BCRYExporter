# ------------------------------------------------------------------------------
# Name:        operators/__init__.py
# Purpose:     Initialization, reloading, and registration of all operator submodules
# ------------------------------------------------------------------------------

if "bpy" in locals():
    import importlib

    # Explicitly import submodules into current namespace before reloading to prevent NameError on script reloads
    from . import export_ops, mesh_ops, bone_ops, material_ops, proxy_ops

    importlib.reload(export_ops)
    importlib.reload(mesh_ops)
    importlib.reload(bone_ops)
    importlib.reload(material_ops)
    importlib.reload(proxy_ops)
else:
    import bpy
    from . import export_ops, mesh_ops, bone_ops, material_ops, proxy_ops

# Tuples of our cleanly segregated operator submodules
submodules = (
    export_ops,
    mesh_ops,
    bone_ops,
    material_ops,
    proxy_ops,
)


def register():
    """Dynamically registers all custom Operator classes from the submodules."""
    for sub in submodules:
        if hasattr(sub, "classes"):
            for cls in sub.classes:
                bpy.utils.register_class(cls)


def unregister():
    """Dynamically unregisters all custom Operator classes from the submodules."""
    # Unregister submodules in reverse order to protect dependency structures
    for sub in reversed(submodules):
        if hasattr(sub, "classes"):
            for cls in reversed(sub.classes):
                bpy.utils.unregister_class(cls)
