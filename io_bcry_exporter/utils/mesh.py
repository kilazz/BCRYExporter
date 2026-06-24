# ------------------------------------------------------------------------------
# Name:        utils/mesh.py
# Purpose:     Mesh evaluations, BMesh helpers, normal arrays, and cleanups
# ------------------------------------------------------------------------------

import bpy
import bmesh


def get_bmesh(object_, apply_modifiers=False):
    """Retrieves a BMesh representation of a mesh object.

    Temporarily applies edge split operators to bridge the Blender 4.1+
    'Smooth by Angle' modifier behavior to standard CryEngine-compatible geometries.
    """
    # Ensure object is active to set context safely
    bpy.context.view_layer.objects.active = object_

    # Smooth by Angle workaround
    bcry_split_modifier(object_)

    depsgraph = bpy.context.evaluated_depsgraph_get()

    if apply_modifiers:
        object_eval = object_.evaluated_get(depsgraph)
        mesh = object_eval.to_mesh()
        bmesh_ = bmesh.new()
        bmesh_.from_mesh(mesh)
    else:
        mesh = object_.to_mesh()
        bmesh_ = bmesh.new()
        bmesh_.from_mesh(mesh)

    return bmesh_


def clear_bmesh(object_, bmesh_):
    """Disposes of the allocated BMesh and restores the original modifier layout."""
    remove_bcry_split_modifier(object_)
    object_.to_mesh_clear()


def bcry_split_modifier(object_):
    """Replaces Blender's 'Smooth by Angle' node group with an equivalent EDGE_SPLIT modifier.

    This ensures smooth normals are preserved correctly on export.
    """
    has_smooth_by_angle_modifier = False
    split_angle = 0
    use_edge_angle = False
    use_edge_sharp = False

    for modifier in list(object_.modifiers):
        # 'Smooth by Angle' is an Essential geometry node group, matched by prefix
        if modifier.name.startswith("Smooth by Angle"):
            use_edge_angle = True
            use_edge_sharp = not modifier["Socket_1"]
            split_angle = modifier["Input_1"]
            has_smooth_by_angle_modifier = True
            object_.modifiers.remove(modifier)
            break

    if has_smooth_by_angle_modifier:
        edge_split_modifier = object_.modifiers.new("BCRY_EDGE_SPLIT", "EDGE_SPLIT")
        edge_split_modifier.use_edge_angle = use_edge_angle
        edge_split_modifier.use_edge_sharp = use_edge_sharp
        edge_split_modifier.split_angle = split_angle


def remove_bcry_split_modifier(object_):
    """Cleans up the temporary EDGE_SPLIT modifier and restores the original node modifier."""
    edge_split_modifier = object_.modifiers.get("BCRY_EDGE_SPLIT")
    if edge_split_modifier:
        active_object = bpy.context.active_object
        bpy.context.view_layer.objects.active = object_

        # Restore the native geometry node group
        bpy.ops.object.modifier_add_node_group(
            asset_library_type="ESSENTIALS",
            asset_library_identifier="",
            relative_asset_identifier="geometry_nodes\\smooth_by_angle.blend\\NodeTree\\Smooth by Angle",
        )

        for modifier in object_.modifiers:
            if modifier.name.startswith("Smooth by Angle"):
                modifier.name = "Smooth by Angle"
                modifier["Input_1"] = edge_split_modifier.split_angle
                modifier["Socket_1"] = not edge_split_modifier.use_edge_sharp
                bpy.context.view_layer.objects.active = active_object
                break

        object_.modifiers.remove(edge_split_modifier)


def get_tessfaces(bmesh_):
    """Calculates loop triangles and maps them to face-index-aligned arrays."""
    tessfaces = []
    tfs = bmesh_.calc_loop_triangles()

    for face in bmesh_.faces:
        tessfaces.append([])

    for tf in tfs:
        vert_list = []
        for loop in tf:
            vert_list.append(loop.vert.index)

        tessfaces[tf[0].face.index].append(vert_list)

    return tessfaces


def get_custom_normals(bmesh_, use_edge_angle, split_angle):
    """Extracts custom vertex normal vectors. Supported out-of-the-box by Blender 4.x."""
    float_normals = []

    for face in bmesh_.faces:
        for vertex in face.verts:
            float_normals.extend(vertex.normal.normalized())

    return float_normals


def get_normal_array(bmesh_, use_edge_angle, use_edge_sharp, split_angle):
    """Retrieves raw normalized vertex vector layouts."""
    float_normals = []

    for face in bmesh_.faces:
        for vertex in face.verts:
            float_normals.extend(vertex.normal.normalized())

    return float_normals


def check_sharp_edges(vertex, current_face, previous_face, target_face):
    """Helper recursion to identify split border edges."""
    for trans_edge in current_face.edges:
        if trans_edge in vertex.link_edges:
            for neighbor_face in trans_edge.link_faces:
                if neighbor_face == current_face or neighbor_face == previous_face:
                    continue
                if trans_edge.smooth:
                    if neighbor_face == target_face:
                        return True
                    else:
                        new_previous_face = current_face
                        return check_sharp_edges(
                            vertex, neighbor_face, new_previous_face, target_face
                        )

    return False


def remove_unused_meshes():
    """Removes orphan meshes with 0 users to free system memory."""
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def remove_unused_actions():
    """Cleans up temporary animation actions containing the '+bcry' tag."""
    for action in bpy.data.actions:
        if "+bcry" in action.name:
            bpy.data.actions.remove(action)
