# ------------------------------------------------------------------------------
# Name:        utils/math.py
# Purpose:     Matrix, vector, and numerical formatting helpers
# ------------------------------------------------------------------------------

import math
import bpy
from xml.dom.minidom import Document
from mathutils import Matrix, Vector

# Constant conversion factor from radians to degrees
to_degrees = 180.0 / math.pi


def transform_bone_matrix(bone):
    """Aligns a Blender bone's coordinate system with CryEngine requirements.

    Transforms the bone matrix to orient the axes properly for the engine structure.
    """
    if not bone.parent:
        return Matrix()

    i1 = Vector((1.0, 0.0, 0.0))
    i2 = Vector((0.0, 1.0, 0.0))
    i3 = Vector((0.0, 0.0, 1.0))

    x_axis = bone.y_axis
    y_axis = bone.x_axis
    z_axis = -bone.z_axis

    row_x = Vector((x_axis @ i1, x_axis @ i2, x_axis @ i3))
    row_y = Vector((y_axis @ i1, y_axis @ i2, y_axis @ i3))
    row_z = Vector((z_axis @ i1, z_axis @ i2, z_axis @ i3))

    trans_matrix = Matrix((row_x, row_y, row_z))

    location = trans_matrix @ bone.matrix.translation
    bone_matrix = trans_matrix.to_4x4()
    bone_matrix.translation = -location

    return bone_matrix


def transform_animation_matrix(matrix):
    """Modifies an animation matrix to map correctly to CryEngine's layout.

    Rotates Z and X axes to bridge the orientation gap.
    """
    eu = matrix.to_euler()
    eu.rotate_axis("Z", math.pi / 2.0)
    eu.rotate_axis("X", math.pi)

    new_matrix = eu.to_matrix()
    new_matrix = new_matrix.to_4x4()
    new_matrix.translation = matrix.translation

    return new_matrix


def frame_to_time(frame):
    """Converts a Blender timeline frame number to its exact time value in seconds."""
    fps_base = bpy.context.scene.render.fps_base
    fps = bpy.context.scene.render.fps
    return fps_base * frame / fps


def matrix_to_string(matrix):
    """Converts a mathutils Matrix into a plain string array representation."""
    return str(matrix_to_array(matrix))


def floats_to_string(floats, separator=" ", precision="%.6f"):
    """Formating utility to convert a list of floats into a single string."""
    return separator.join(precision % x for x in floats)


def strings_to_string(strings, separator=" "):
    """Joins a list of strings using the specified delimiter."""
    return separator.join(string for string in strings)


def matrix_to_array(matrix):
    """Flattens a multi-dimensional mathutils Matrix into a flat 1D Python list."""
    array = []
    for row in matrix:
        array.extend(row)

    return array


def write_matrix(matrix, node):
    """Appends a flattened matrix representation to an XML DOM element node."""
    doc = Document()
    for row in matrix:
        row_string = floats_to_string(row)
        node.appendChild(doc.createTextNode(row_string))


def join(*items):
    """Helper to join arbitrary values together as a single unified string."""
    strings = []
    for item in items:
        strings.append(str(item))
    return "".join(strings)


def get_bounding_box(object_):
    """Extracts the minimum and maximum spatial coordinates (bounding box) of an object.

    Supports both meshes and empty helper nodes (using empty display size).
    """
    vmin = Vector()
    vmax = Vector()
    if object_.type == "EMPTY":
        k = object_.empty_display_size
        vmax = Vector((k, k, k))
        vmin = Vector((-k, -k, -k))
    elif object_.type == "MESH":
        box = object_.bound_box
        vmin = Vector([box[0][0], box[0][1], box[0][2]])
        vmax = Vector([box[6][0], box[6][1], box[6][2]])

    return vmin[0], vmin[1], vmin[2], vmax[0], vmax[1], vmax[2]


def calc_optimal_bone_radius(bone_head_ws, bone_tail_ws, verts_ws):
    """Calculates the optimal proxy radius for a bone based on its weighted vertex cluster.

    Uses the perpendicular distance of the bone vector to each assigned vertex,
    sorting and taking the 85th percentile to automatically exclude outliers
    or geometric spikes.

    Args:
        bone_head_ws (Vector): World space coordinates of the bone head.
        bone_tail_ws (Vector): World space coordinates of the bone tail.
        verts_ws (list of Vector): Vertices weighted to this bone in world space.

    Returns:
        float: Optimal radius for the physical collision proxy.
    """
    if not verts_ws:
        return 0.0

    bone_vec = bone_tail_ws - bone_head_ws
    bone_len_sq = bone_vec.length_squared

    if bone_len_sq < 0.0001:
        distances = [(v - bone_head_ws).length for v in verts_ws]
    else:
        distances = []
        for v in verts_ws:
            ap = v - bone_head_ws
            t = ap.dot(bone_vec) / bone_len_sq
            t = max(0.0, min(1.0, t))
            closest_point = bone_head_ws + t * bone_vec
            distances.append((v - closest_point).length)

    if not distances:
        return 0.0

    distances.sort()
    # 85th percentile handles edge geometry spikes smoothly without ballooning the collision volume
    idx = int(len(distances) * 0.85)
    return distances[idx]
