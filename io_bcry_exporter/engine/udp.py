# ------------------------------------------------------------------------------
# Name:        engine/udp.py
# Purpose:     Manages User Defined Properties (UDP) and Bone Inverse Kinematics (IK)
# ------------------------------------------------------------------------------

import math


def get_udp(object_, udp_name, udp_value, is_checked=None):
    """Retrieves a User Defined Property from a Blender object.

    Acts as an overloaded method supporting simple existence checks
    and key-value evaluation.
    """
    if is_checked is None:
        # Check for property existence
        if udp_name in object_:
            udp_value = True
        else:
            udp_value = False
        return udp_value

    else:
        # Check and extract property value
        if udp_name in object_:
            udp_value = object_[udp_name]
            is_checked = True
        else:
            is_checked = False
        return udp_value, is_checked


def edit_udp(object_, udp_name, udp_value, is_checked=True):
    """Edits or removes a User Defined Property on a Blender object."""
    if is_checked:
        object_[udp_name] = udp_value
    else:
        if udp_name in object_:
            del object_[udp_name]


def is_user_defined_property(property_name):
    """Checks if a Blender property corresponds to a registered CryEngine UDP parameter."""
    prop_list = [
        "phys_proxy",
        "colltype_player",
        "no_explosion_occlusion",
        "entity",
        "mass",
        "density",
        "pieces",
        "dynamic",
        "no_hit_refinement",
        "limit",
        "bend",
        "twist",
        "pull",
        "push",
        "shift",
        "player_can_break",
        "gameplay_critical",
        "constraint_limit",
        "constraint_minang",
        "consrtaint_maxang",
        "constraint_damping",
        "constraint_collides",
        "stiffness",
        "hardness",
        "max_stretch",
        "max_impulse",
        "skin_dist",
        "thickness",
        "explosion_scale",
        "notaprim",
        "hull",
        "wheel",
    ]

    return property_name in prop_list


def get_bone_ik_max_min(pose_bone):
    """Resolves minimum and maximum degree angles for skeletal Inverse Kinematics joints."""
    x_ik = y_ik = z_ik = ""

    if pose_bone.lock_ik_x:
        x_ik = f"_xmax={0.0:f}_xmin={0.0:f}"
    else:
        x_ik = f"_xmax={math.degrees(-pose_bone.ik_min_y):.4f}_xmin={math.degrees(-pose_bone.ik_max_y):.4f}"

    if pose_bone.lock_ik_y:
        y_ik = f"_ymax={0.0:f}_ymin={0.0:f}"
    else:
        y_ik = f"_ymax={math.degrees(-pose_bone.ik_min_x):.4f}_ymin={math.degrees(-pose_bone.ik_max_x):.4f}"

    if pose_bone.lock_ik_z:
        z_ik = f"_zmax={0.0:f}_zmin={0.0:f}"
    else:
        z_ik = f"_zmax={math.degrees(pose_bone.ik_max_z):.4f}_zmin={math.degrees(pose_bone.ik_min_z):.4f}"

    return x_ik, y_ik, z_ik


def get_bone_ik_properties(pose_bone):
    """Retrieves positional damping and spring tension profiles associated with pose bone ragdolls."""
    damping = [1.0, 1.0, 1.0]
    spring = [0.0, 0.0, 0.0]
    spring_tension = [1.0, 1.0, 1.0]

    if "Damping" in pose_bone:
        damping = pose_bone["Damping"]

    if "Spring" in pose_bone:
        spring = pose_bone["Spring"]

    if "Spring Tension" in pose_bone:
        spring_tension = pose_bone["Spring Tension"]

    return damping, spring, spring_tension
