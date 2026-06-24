# ------------------------------------------------------------------------------
# Name:        core/properties.py
# Purpose:     Defines scene properties and custom data structures
# ------------------------------------------------------------------------------

import bpy
from bpy.props import BoolProperty


class BCRY_ProxyProperties(bpy.types.PropertyGroup):
    """Holds custom viewport toggles used by the physics proxy generation tools."""

    bAdvanced: BoolProperty(
        name="Advanced Options", description="Activate Advanced Options", default=False
    )
    bChild: BoolProperty(
        name="as a Child (for CGA)",
        description="Make new proxy as a child?",
        default=False,
    )
    bSeparate: BoolProperty(
        name="Separate (Only for Mesh)",
        description="Do separate the object?",
        default=False,
    )


def register():
    """Register custom properties with Blender."""
    bpy.utils.register_class(BCRY_ProxyProperties)
    # Attach our property group directly to the Scene context
    bpy.types.Scene.proxy_props = bpy.props.PointerProperty(type=BCRY_ProxyProperties)


def unregister():
    """Remove custom properties from Blender."""
    del bpy.types.Scene.proxy_props
    bpy.utils.unregister_class(BCRY_ProxyProperties)
