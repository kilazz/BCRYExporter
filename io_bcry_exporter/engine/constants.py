# ------------------------------------------------------------------------------
# Name:        engine/constants.py
# Purpose:     UI tooltips and property descriptions for CryEngine parameters
# ------------------------------------------------------------------------------

DESCRIPTIONS = {}

# ------------------------------------------------------------------------------
# Material Physics Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["physDefault"] = (
    "The render geometry is used as physics proxy. This "
    "is expensive for complex objects, so use this only for simple objects "
    "like cubes or if you really need to fully physicalize an object."
)

DESCRIPTIONS["physProxyNoDraw"] = (
    "Mesh is used exclusively for collision detection and is not rendered."
)

DESCRIPTIONS["physNoCollide"] = (
    "Special purpose proxy which is used by the engine to detect player "
    "interaction (e.g. for vegetation touch bending)."
)

DESCRIPTIONS["physObstruct"] = (
    "Used for Soft Cover to block AI view (i.e. on dense foliage)."
)

DESCRIPTIONS["physNone"] = "The render geometry have no physic just render it."

# ------------------------------------------------------------------------------
# Inverse Kinematics Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["spring"] = (
    "Stiffness of an angular spring at a joint can be adjusted via the "
    "'Spring Tension' parameter. A value of 1 means acceleration of "
    "1 radian/second2 (1 radian = 57°)."
)

DESCRIPTIONS["damping"] = (
    "The 'dampening' value in the IK Limit options will effect how loose "
    "the joint will be in the rag doll simulation of the dead body. "
    "Most times you will want the dampening value set at 1.0."
)

# ------------------------------------------------------------------------------
# Physics Proxy Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["notaprim"] = (
    "Force the engine NOT to convert this proxy to a primitive (for example "
    "if the proxy is already naturally box-shaped)."
)

DESCRIPTIONS["no_exp_occlusion"] = (
    "Will allow the force/damage of an explosion to penetrate through the phys proxy."
)

DESCRIPTIONS["colltpye_player"] = (
    "If a phys proxy node has this string, then:\n"
    "1 - This node will only receive player collisions, but no hit impacts.\n"
    "2 - If this object contains other phys proxy nodes, then those other "
    "nodes will not receive player collisions."
)

# ------------------------------------------------------------------------------
# Render Mesh Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["is_entity"] = (
    "If the render geometry properties include 'entity', the "
    "object will not fade out after being disconnected from the main object."
)

DESCRIPTIONS["mass"] = (
    "Mass defines the weight of an object based on real world physics in "
    "kg. mass=0 sets the object to 'unmovable'."
)

DESCRIPTIONS["density"] = (
    "The engine automatically calculates the mass for an object based on the "
    "density and the bounding box of an object. Can be used alternatively to mass."
)

DESCRIPTIONS["pieces"] = (
    "Instead of disconnecting the piece when the joint is broken, it will "
    "instantly disappear spawning a particle effect depending on the "
    "surfacetype of the proxy."
)

DESCRIPTIONS["is_dynamic"] = (
    "This is a special-case string for dynamically breakable meshes "
    "(i.e. glass) - this string flags the object as 'dynamically breakable'. "
    "However this string is not required on Glass, Trees, or Cloth, as "
    "these are already flagged automatically by the engine (through "
    "surface-type system)."
)

DESCRIPTIONS["no_hit_refinement"] = (
    "If the render geometry properties include 'entity', the object will "
    "not fade out after being disconnected from the main object."
)

DESCRIPTIONS["other_rendermesh"] = (
    "(Mostly obsolete now) - This would be required if the phys proxy is "
    "a sibling of the rendermesh. Proxies should always be children of the "
    "rendermesh however, in which case other_rendermesh is not required."
)

# ------------------------------------------------------------------------------
# Joint Node Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["limit"] = (
    "Limit is a general value for several different kind of forces applied "
    "to the joint. It contains a combination of the values below."
)

DESCRIPTIONS["bend"] = "Maximum torque around an axis perpendicular to the normal."

DESCRIPTIONS["twist"] = "Maximum torque around the normal."

DESCRIPTIONS["pull"] = (
    "Maximum force applied to the joint's 1st object against the joint normal "
    "(the parts are 'pulled together' as a reaction to external forces "
    "pulling them apart)."
)

DESCRIPTIONS["push"] = (
    "Maximum force applied to the joint's 1st object along the joint normal; "
    "joint normal is the joint's z axis, so for this value to actually be "
    "'push apart', this axis must be directed inside the 1st object."
)

DESCRIPTIONS["shift"] = "Maximum force in the direction perpendicular to normal."

DESCRIPTIONS["player_can_break"] = (
    "Joints in the entire breakable entity can be broken by the player "
    "bumping into them."
)

DESCRIPTIONS["gameplay_critical"] = (
    "Joints in the entire entity will break, even if jointed breaking is "
    "disabled overall."
)

# ------------------------------------------------------------------------------
# Deformable Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["stiffness"] = "Resilience to bending and shearing (default 10)."

DESCRIPTIONS["hardness"] = "Resilience to stretching (default 10)."

DESCRIPTIONS["max_stretch"] = (
    "If any edge is stretched more than that, it's length is re-enforced. "
    "max_stretch = 0.3 means stretched to 130% of its original length."
)

DESCRIPTIONS["max_impulse"] = (
    "Upper limit on all applied impulses. Default skeleton's mass*100."
)

DESCRIPTIONS["skin_dist"] = (
    "Sphere radius in skinning assignment. Default is the minimum of "
    "the main mesh's bounding box's dimensions."
)

DESCRIPTIONS["thickness"] = (
    "Sets the collision thickness for the skeleton. Setting thickness to 0 "
    "disables all collisions."
)

DESCRIPTIONS["explosion_scale"] = (
    "Used to scale down the effect of explosions on the deformable. This "
    "lets you have visible deformations from bullet impacts, but without "
    "vastly distorting the object too far with explosions."
)

# ------------------------------------------------------------------------------
# Animation Range Type Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["range_timeline"] = (
    "Animation range is set from Timeline Editor. You may directly change "
    "start and end frame from Timeline Editor. This is best choice for "
    "single animation per file."
)

DESCRIPTIONS["range_values"] = (
    "Animation range is stored in custom properties values. You must enter "
    "animation range values. You can change start or end frame from object "
    "custom properties. This is ideal for multiple animations in a "
    "blender project."
)

DESCRIPTIONS["range_markers"] = (
    "Animation range is on stored animation markers. Markers can directly "
    "be set on Timeline Editor to change frame range."
)

# ------------------------------------------------------------------------------
# Locator Locomotion Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["locator_length"] = (
    "The Locator Locomotion bone length to represented in 3D view."
)

DESCRIPTIONS["locator_root"] = (
    "Skeleton Root Bone: The Locator Locomotion bone is going to be "
    "linked/parented to that bone."
)

DESCRIPTIONS["locator_move"] = (
    "Movement Reference Bone: The Locator Locomotion use that bone to "
    "copy movements from selected axis."
)

# ------------------------------------------------------------------------------
# General Export Descriptions
# ------------------------------------------------------------------------------
DESCRIPTIONS["merge_all_nodes"] = (
    "Compiles all the geometry from the different nodes into a single node "
    "which improves the efficiency. It's supported only for non-skinned "
    "geometry. For more information on Merge All Nodes, please refer to the "
    "official CryEngine documentation."
)
