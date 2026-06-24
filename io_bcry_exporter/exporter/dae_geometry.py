# ------------------------------------------------------------------------------
# Name:        exporter/dae_geometry.py
# Purpose:     COLLADA static/skinned geometry compiler and scene graph writer
# ------------------------------------------------------------------------------

import os
from time import process_time

import bpy
from mathutils import Matrix

from ..core import exceptions
from ..core.logger import bcPrint
from ..engine.compiler import RCInstance
from ..engine import udp
from .. import utils
from .dae_base import CrytekDaeExporterBase


class CrytekDaeExporter(CrytekDaeExporterBase):
    """COLLADA Exporter class specializing in static, animated, and skinned geometries."""

    def __init__(self, config):
        super().__init__(config)
        print("CrytekDaeExporter initialized.")

    def export(self):
        """Executes the complete geometry compilation pass writing DAE structures to disk."""
        self._prepare_for_export()

        root_element = self._doc.createElement("collada")
        root_element.setAttribute(
            "xmlns", "http://www.collada.org/2005/11/COLLADASchema"
        )
        root_element.setAttribute("version", "1.4.1")
        self._doc.appendChild(root_element)

        # Populate COLLADA boilerplate
        self._create_file_header(root_element)

        if self._config.generate_materials:
            self._m_exporter.generate_materials()

        self._export_library_cameras(root_element)
        self._export_library_lights(root_element)
        self._export_library_images(root_element)
        self._export_library_effects(root_element)
        self._export_library_materials(root_element)

        # Export geometry nodes
        self._export_library_geometries(root_element)

        utils.add_fakebones()
        try:
            self._export_library_controllers(root_element)
            self._export_library_animation_clips_and_animations(root_element)
            self._export_library_visual_scenes(root_element)
        except RuntimeError as e:
            bcPrint(f"RuntimeError during scene graph export: {e}", "warning")
        finally:
            utils.remove_fakebones()

        self._export_scene(root_element)

        # Trigger RC compiler
        converter = RCInstance(self._config)
        converter.convert_dae(self._doc)

        self._write_scripts()

    def _prepare_for_export(self):
        """Sanitizes names and normalizes vertex group weights."""
        utils.clean_file(self._config.export_selected_nodes)

        if self._config.fix_weights:
            utils.fix_weights()

    def _write_scripts(self):
        """Triggers standard base configurations on complete operations."""
        config = self._config
        filepath = utils.strip_extension_from_path(config.filepath)

        if config.make_chrparams:
            chrparams_path = f"{filepath}.chrparams"
            chr_contents = utils.generate_file_contents("chrparams")
            utils.generate_file(chrparams_path, chr_contents)

        if config.make_cdf:
            cdf_path = f"{filepath}.cdf"
            cdf_contents = utils.generate_file_contents("cdf")
            utils.generate_file(cdf_path, cdf_contents)

    # ------------------------------------------------------------------------------
    # Library Geometries
    # ------------------------------------------------------------------------------

    def _export_library_geometries(self, parent_element):
        """Assembles the primary geometric meshes library, building normal/UV streams."""
        libgeo = self._doc.createElement("library_geometries")
        parent_element.appendChild(libgeo)

        for collection in utils.get_mesh_export_nodes(
            self._config.export_selected_nodes
        ):
            for object_ in collection.objects:
                if object_.type != "MESH":
                    continue

                apply_modifiers = self._config.apply_modifiers
                if utils.get_node_type(collection) in ("chr", "skin"):
                    apply_modifiers = False

                bmesh_ = utils.get_bmesh(object_, apply_modifiers)
                geometry_node = self._doc.createElement("geometry")
                geometry_name = utils.get_geometry_name(collection, object_)
                geometry_node.setAttribute("id", geometry_name)
                mesh_node = self._doc.createElement("mesh")

                print()
                bcPrint(f'"{object_.name}" object is being processed...')

                start_time = process_time()
                self._write_positions(bmesh_, mesh_node, geometry_name)
                bcPrint(f"Positions written: {process_time() - start_time:.4f}s")

                start_time = process_time()
                self._write_normals(object_, bmesh_, mesh_node, geometry_name)
                bcPrint(f"Normals written: {process_time() - start_time:.4f}s")

                start_time = process_time()
                self._write_uvs(object_, bmesh_, mesh_node, geometry_name)
                bcPrint(f"UVs written: {process_time() - start_time:.4f}s")

                start_time = process_time()
                self._write_vertex_colors(object_, bmesh_, mesh_node, geometry_name)
                bcPrint(f"Colors written: {process_time() - start_time:.4f}s")

                start_time = process_time()
                self._write_vertices(mesh_node, geometry_name)
                bcPrint(f"Vertices written: {process_time() - start_time:.4f}s")

                start_time = process_time()
                self._write_triangle_list(object_, bmesh_, mesh_node, geometry_name)
                bcPrint(f"Triangle list written: {process_time() - start_time:.4f}s")

                extra = self._create_double_sided_extra("MAYA")
                mesh_node.appendChild(extra)
                geometry_node.appendChild(mesh_node)
                libgeo.appendChild(geometry_node)

                utils.clear_bmesh(object_, bmesh_)
                bcPrint(
                    f'"{object_.name}" object complete for node "{collection.name}".'
                )

    def _write_positions(self, bmesh_, mesh_node, geometry_name):
        """Extracts and writes absolute vertex coordinates."""
        float_positions = []
        for vertex in bmesh_.verts:
            float_positions.extend(vertex.co)

        id_ = f"{geometry_name}-pos"
        source = utils.write_source(id_, "float", float_positions, "XYZ")
        mesh_node.appendChild(source)

    def _write_normals(self, object_, bmesh_, mesh_node, geometry_name):
        """Assembles face-vertex normals, matching active split parameters."""
        use_edge_angle = False
        split_angle = 0
        use_edge_sharp = False

        for modifier in object_.modifiers:
            if modifier.type == "EDGE_SPLIT" and modifier.show_viewport:
                use_edge_angle |= modifier.use_edge_angle
                use_edge_sharp |= modifier.use_edge_sharp
                split_angle = modifier.split_angle
                break

        if self._config.custom_normals:
            float_normals = utils.get_custom_normals(
                bmesh_, use_edge_angle, split_angle
            )
        else:
            float_normals = utils.get_normal_array(
                bmesh_, use_edge_angle, use_edge_sharp, split_angle
            )

        id_ = f"{geometry_name}-normal"
        source = utils.write_source(id_, "float", float_normals, "XYZ")
        mesh_node.appendChild(source)

    def _write_uvs(self, object_, bmesh_, mesh_node, geometry_name):
        """Assembles UV maps, ensuring a default channel is generated if missing."""
        uv_layer = bmesh_.loops.layers.uv.active
        if object_.data.uv_layers.active is None:
            bcPrint(
                f"Object {object_.name} lacks a UV map, generating default layout...",
                "warning",
            )
            uv_layer = bmesh_.loops.layers.uv.new()

        float_uvs = []
        for face in bmesh_.faces:
            for loop in face.loops:
                float_uvs.extend(loop[uv_layer].uv)

        id_ = f"{geometry_name}-uvs"
        source = utils.write_source(id_, "float", float_uvs, "ST")
        mesh_node.appendChild(source)

    def _write_vertex_colors(self, object_, bmesh_, mesh_node, geometry_name):
        """Assembles vertex colors, mapping custom visual element alphas."""
        float_colors = []
        alpha_found = False

        active_layer = bmesh_.loops.layers.color.active
        if object_.data.vertex_colors:
            if active_layer.name.lower() == "alpha":
                alpha_found = True
                for vert in bmesh_.verts:
                    loop = vert.link_loops[0]
                    color = loop[active_layer]
                    alpha_color = (color[0] + color[1] + color[2]) / 3.0
                    float_colors.extend([1.0, 1.0, 1.0, alpha_color])
            else:
                for vert in bmesh_.verts:
                    if len(vert.link_loops) == 0:
                        bcPrint(
                            f"Mesh Warning: Vert {vert.index} lacks link loops. Clean mesh before export.",
                            "warning",
                        )
                        continue
                    loop = vert.link_loops[0]
                    color = loop[active_layer]
                    float_colors.extend([color[0], color[1], color[2]])

        if float_colors:
            id_ = f"{geometry_name}-vcol"
            params = "RGBA" if alpha_found else "RGB"
            source = utils.write_source(id_, "float", float_colors, params)
            mesh_node.appendChild(source)

    def _write_vertices(self, mesh_node, geometry_name):
        """Declares vertices references."""
        vertices = self._doc.createElement("vertices")
        vertices.setAttribute("id", f"{geometry_name}-vtx")
        input = utils.write_input(geometry_name, None, "pos", "POSITION")
        vertices.appendChild(input)
        mesh_node.appendChild(vertices)

    def _write_triangle_list(self, object_, bmesh_, mesh_node, geometry_name):
        """Generates indices representing triangles."""
        tessfaces = utils.get_tessfaces(bmesh_)
        current_material_index = 0

        for material, materialname in self._m_exporter.get_materials_for_object(
            object_
        ).items():
            # Avoid string concatenation inside tight loop to prevent huge export delays
            triangles_list = []
            triangle_count = 0
            normal_uv_index = 0

            for face in bmesh_.faces:
                norm_uv_indices = {}
                for index in range(0, len(face.verts)):
                    # Direct integer indexing instead of cast-to-string operations
                    norm_uv_indices[face.verts[index].index] = normal_uv_index + index

                if face.material_index == current_material_index:
                    for tessface in tessfaces[face.index]:
                        triangle_count += 1
                        for vert in tessface:
                            normal_uv = norm_uv_indices[vert]
                            dae_vertex = self._write_vertex_data(
                                vert,
                                normal_uv,
                                normal_uv,
                                object_.data.vertex_colors,
                            )
                            triangles_list.append(dae_vertex)

                normal_uv_index += len(face.verts)

            current_material_index += 1

            if triangle_count == 0:
                continue

            triangle_list = self._doc.createElement("triangles")
            triangle_list.setAttribute("material", materialname)
            triangle_list.setAttribute("count", str(triangle_count))

            inputs = []
            inputs.append(utils.write_input(geometry_name, 0, "vtx", "VERTEX"))
            inputs.append(utils.write_input(geometry_name, 1, "normal", "NORMAL"))
            inputs.append(utils.write_input(geometry_name, 2, "uvs", "TEXCOORD"))
            if object_.data.vertex_colors:
                inputs.append(utils.write_input(geometry_name, 3, "vcol", "COLOR"))

            for input in inputs:
                triangle_list.appendChild(input)

            p = self._doc.createElement("p")
            p_text = self._doc.createTextNode("".join(triangles_list))
            p.appendChild(p_text)

            triangle_list.appendChild(p)
            mesh_node.appendChild(triangle_list)

    def _write_vertex_data(self, vert, normal, _uv, vertex_colors):
        """Assembles structured triangle index components."""
        if vertex_colors:
            return f"{vert:d} {normal:d} {_uv:d} {vert:d} "
        else:
            return f"{vert:d} {normal:d} {_uv:d} "

    def _create_double_sided_extra(self, profile):
        """Forces double-sided rendering parameters inside target profile structures."""
        extra = self._doc.createElement("extra")
        technique = self._doc.createElement("technique")
        technique.setAttribute("profile", profile)

        double_sided = self._doc.createElement("double_sided")
        double_sided_value = self._doc.createTextNode("1")
        double_sided.appendChild(double_sided_value)

        technique.appendChild(double_sided)
        extra.appendChild(technique)
        return extra

    # ------------------------------------------------------------------------------
    # Library Controllers (Bone Matrices, Bindings, Skinned Weights)
    # ------------------------------------------------------------------------------

    def _export_library_controllers(self, parent_element):
        """Assembles <library_controllers> managing skinned bone dependencies."""
        library_node = self._doc.createElement("library_controllers")

        ALLOWED_NODE_TYPES = ("chr", "skin")
        for collection in utils.get_mesh_export_nodes(
            self._config.export_selected_nodes
        ):
            node_type = utils.get_node_type(collection)
            if node_type in ALLOWED_NODE_TYPES:
                for object_ in collection.objects:
                    if utils.is_fakebone(object_):
                        continue
                    if not utils.is_bone_geometry(object_):
                        armature = utils.get_armature_for_object(object_)
                        if armature is not None:
                            self._process_bones(
                                library_node, collection, object_, armature
                            )
        parent_element.appendChild(library_node)

    def _process_bones(self, parent_node, group, object_, armature):
        """Binds a mesh object with its tracking armature skeletal layout."""
        id_ = f"{armature.name}_{object_.name}"

        controller_node = self._doc.createElement("controller")
        parent_node.appendChild(controller_node)
        controller_node.setAttribute("id", id_)

        skin_node = self._doc.createElement("skin")
        skin_node.setAttribute("source", f"#{utils.get_geometry_name(group, object_)}")
        controller_node.appendChild(skin_node)

        bind_shape_matrix = self._doc.createElement("bind_shape_matrix")
        utils.write_matrix(Matrix(), bind_shape_matrix)
        skin_node.appendChild(bind_shape_matrix)

        self._process_bone_joints(object_, armature, skin_node, group)
        self._process_bone_matrices(object_, armature, skin_node)
        self._process_bone_weights(object_, armature, skin_node)

        joints = self._doc.createElement("joints")
        input = utils.write_input(id_, None, "joints", "JOINT")
        joints.appendChild(input)
        input = utils.write_input(id_, None, "matrices", "INV_BIND_MATRIX")
        joints.appendChild(input)
        skin_node.appendChild(joints)

    def _process_bone_joints(self, _object, armature, skin_node, group):
        """Populates custom JOINT bone name arrays."""
        bones = utils.get_bones(armature)
        id_ = f"{armature.name}_{_object.name}-joints"
        bone_names = []
        for bone in bones:
            bone_name = self._get_dae_bone_name(bone, group)
            bone_names.append(bone_name)
        source = utils.write_source(id_, "IDREF", bone_names, [])
        skin_node.appendChild(source)

    def _process_bone_matrices(self, _object, armature, skin_node):
        """Calculates and writes bone inverse bind transform matrices."""
        bone_matrices = []
        bones = utils.get_bones(armature)
        for bone in bones:
            pose_bone = armature.pose.bones.get(bone.name)
            if pose_bone:
                bone_matrix = utils.transform_bone_matrix(pose_bone)
                bone_matrices.extend(utils.matrix_to_array(bone_matrix))

        id_ = f"{armature.name}_{_object.name}-matrices"
        source = utils.write_source(id_, "float4x4", bone_matrices, [])
        skin_node.appendChild(source)

    def _process_bone_weights(self, _object, armature, skin_node):
        """Assembles skinned bone vertex weight indices."""
        bones = utils.get_bones(armature)
        group_weights = []

        # Performance optimization - replace slow string concatenation loops
        # with high-performance list structures to support highly complex meshes.
        vw_list = []
        vgroups_lengths_list = []
        vertex_count = 0
        bone_list = {bone.name: i for i, bone in enumerate(bones)}

        for vertex in _object.data.vertices:
            vertex_group_count = 0
            for group in vertex.groups:
                group_name = _object.vertex_groups[group.group].name
                if group.weight == 0 or group_name not in bone_list:
                    continue
                if vertex_group_count == 8:
                    bcPrint(
                        f"Weight Warning: Exceeded maximum 8 weights limit on {_object.name}!",
                        "warning",
                    )
                    continue
                group_weights.append(group.weight)
                vw_list.append(f"{bone_list[group_name]} {vertex_count} ")
                vertex_count += 1
                vertex_group_count += 1

            vgroups_lengths_list.append(f"{vertex_group_count} ")

        # Compile flat output streams
        vw = "".join(vw_list)
        vgroups_lengths = "".join(vgroups_lengths_list)

        id_ = f"{armature.name}_{_object.name}-weights"
        source = utils.write_source(id_, "float", group_weights, [])
        skin_node.appendChild(source)

        vertex_weights = self._doc.createElement("vertex_weights")
        vertex_weights.setAttribute("count", str(len(_object.data.vertices)))

        id_base = f"{armature.name}_{_object.name}"
        input = utils.write_input(id_base, 0, "joints", "JOINT")
        vertex_weights.appendChild(input)
        input = utils.write_input(id_base, 1, "weights", "WEIGHT")
        vertex_weights.appendChild(input)

        vcount = self._doc.createElement("vcount")
        vcount_text = self._doc.createTextNode(vgroups_lengths)
        vcount.appendChild(vcount_text)
        vertex_weights.appendChild(vcount)

        v = self._doc.createElement("v")
        v_text = self._doc.createTextNode(vw)
        v.appendChild(v_text)
        vertex_weights.appendChild(v)

        skin_node.appendChild(vertex_weights)

    # ------------------------------------------------------------------------------
    # Library Animations (Placeholder for static geometry compiling)
    # ------------------------------------------------------------------------------

    def _export_library_animation_clips_and_animations(self, parent_element):
        """Assembles library placeholders."""
        libanmcl = self._doc.createElement("library_animation_clips")
        libanm = self._doc.createElement("library_animations")
        parent_element.appendChild(libanmcl)
        parent_element.appendChild(libanm)

    # ------------------------------------------------------------------------------
    # Library Visual Scenes (Visual Node Hierarchy Graph)
    # ------------------------------------------------------------------------------

    def _export_library_visual_scenes(self, parent_element):
        """Assembles <library_visual_scenes> building standard hierarchy layouts."""
        current_element = self._doc.createElement("library_visual_scenes")
        visual_scene = self._doc.createElement("visual_scene")
        visual_scene.setAttribute("id", "scene")
        visual_scene.setAttribute("name", "scene")
        current_element.appendChild(visual_scene)
        parent_element.appendChild(current_element)

        if utils.get_mesh_export_nodes(self._config.export_selected_nodes):
            if utils.are_duplicate_nodes():
                bpy.ops.bcry.display_error(
                    "INVOKE_DEFAULT",
                    message="Export Aborted: Multiple export nodes share identical names.",
                )
                raise exceptions.BCryException("Duplicate node names found!")

            for group in utils.get_mesh_export_nodes(
                self._config.export_selected_nodes
            ):
                self._write_export_node(group, visual_scene)

    def _write_export_node(self, group, visual_scene):
        """Creates parent CryExportNode layout references."""
        if not self._config.export_for_lumberyard:
            node_name = f"CryExportNode_{utils.get_node_name(group)}"
            node = self._doc.createElement("node")
            node.setAttribute("id", node_name)
            node.setIdAttribute("id")
        else:
            node_name = f"{utils.get_node_name(group)}"
            node = self._doc.createElement("node")
            node.setAttribute("id", node_name)
            node.setAttribute("LumberyardExportNode", "1")
            node.setIdAttribute("id")

        root_objects = []
        for object_ in group.objects:
            if utils.is_visual_scene_node_writed(object_, group):
                root_objects.append(object_)

        node = self._write_visual_scene_node(root_objects, node, group)

        extra = self._create_cryengine_extra(group)
        node.appendChild(extra)
        visual_scene.appendChild(node)

    def _write_visual_scene_node(self, objects, parent_node, group):
        """Iterates and builds layout nodes for mesh objects (with parent-independent armature resolver)."""
        for object_ in objects:
            if (
                (object_.type == "MESH" or object_.type == "EMPTY")
                and not utils.is_fakebone(object_)
                and not utils.is_lod_geometry(object_)
                and not utils.is_there_a_parent_releation(object_, group)
            ):
                prop_name = object_.name
                node_type = utils.get_node_type(group)
                if node_type in ("chr", "skin"):
                    prop_name = (
                        f"{object_.name}{self._create_properties_name(object_, group)}"
                    )

                node = self._doc.createElement("node")
                node.setAttribute("id", prop_name)
                node.setAttribute("name", prop_name)
                node.setIdAttribute("id")

                self._write_transforms(object_, node)

                if not utils.is_dummy(object_):
                    ALLOWED_NODE_TYPES = ("cgf", "cga", "chr", "skin")
                    if node_type in ALLOWED_NODE_TYPES:
                        instance = self._create_instance(group, object_)
                        if instance is not None:
                            node.appendChild(instance)

                udp_extra = self._create_user_defined_property(object_)
                if udp_extra is not None:
                    node.appendChild(udp_extra)

                parent_node.appendChild(node)

                if utils.is_has_lod(object_):
                    _sub_node = node
                    for lod in utils.get_lod_geometries(object_):
                        _sub_node = self._write_lods(lod, _sub_node, group)

                # Восстановлен умный обход привязки скелета без парентинга через модификатор Armature
                armature = utils.get_armature_for_object(object_)
                if node_type in ("chr", "skin") and armature:
                    self._write_bone_list(
                        [utils.get_root_bone(armature)], object_, parent_node, group
                    )

                    armature_physic = utils.get_armature_physic(armature)
                    if armature_physic:
                        self._write_bone_list(
                            [utils.get_root_bone(armature_physic)],
                            armature_physic,
                            parent_node,
                            group,
                        )
                else:
                    self._write_child_objects(object_, node, group)

        return parent_node

    def _write_child_objects(self, parent_object, parent_node, group):
        """Builds standard parenting links."""
        for child_object in parent_object.children:
            if utils.is_lod_geometry(child_object):
                continue
            if not utils.is_object_in_group(child_object, group):
                continue

            prop_name = child_object.name
            node = self._doc.createElement("node")
            node.setAttribute("id", prop_name)
            node.setAttribute("name", prop_name)
            node.setIdAttribute("id")

            self._write_transforms(child_object, node)

            ALLOWED_NODE_TYPES = ("cgf", "cga", "chr", "skin")
            if utils.get_node_type(group) in ALLOWED_NODE_TYPES:
                instance = self._create_instance(group, child_object)
                if instance is not None:
                    node.appendChild(instance)

            udp_extra = self._create_user_defined_property(child_object)
            if udp_extra is not None:
                node.appendChild(udp_extra)

            self._write_child_objects(child_object, node, group)
            parent_node.appendChild(node)

        return parent_node

    def _write_lods(self, object_, parent_node, group):
        """Assembles visual nodes representing Level of Detail steps."""
        prop_name = utils.changed_lod_name(object_.name)
        node_type = utils.get_node_type(group)
        if node_type in ("chr", "skin"):
            prop_name = f"{object_.name}{self._create_properties_name(object_, group)}"

        node = self._doc.createElement("node")
        node.setAttribute("id", prop_name)
        node.setAttribute("name", prop_name)
        node.setIdAttribute("id")

        self._write_transforms(object_, node)

        ALLOWED_NODE_TYPES = ("cgf", "cga", "chr", "skin")
        if utils.get_node_type(group) in ALLOWED_NODE_TYPES:
            instance = self._create_instance(group, object_)
            if instance is not None:
                node.appendChild(instance)

            udp_extra = self._create_user_defined_property(object_)
            if udp_extra is not None:
                node.appendChild(udp_extra)

            parent_node.appendChild(node)
            return node

    def _write_bone_list(self, bones, object_, parent_node, group):
        """Creates hierarchy lists linking skeletal joints."""
        bone_names = []

        for bone in bones:
            dae_bone_name = self._get_dae_bone_name(bone, group)
            props_ik = self._create_ik_properties(bone, object_)
            bone_name = f"{dae_bone_name}{props_ik}"
            bone_names.append(bone_name)

            node = self._doc.createElement("node")
            node.setAttribute("id", bone_name)
            node.setAttribute("name", bone_name)
            node.setIdAttribute("id")

            fakebone = utils.get_fakebone(bone.name)
            if fakebone is not None:
                self._write_transforms(fakebone, node)

                bone_geometry = utils.get_bone_geometry(bone)
                if bone_geometry is not None:
                    geo_name = utils.get_geometry_name(group, bone_geometry)
                    instance = self._create_bone_instance(bone_geometry, geo_name)
                    node.appendChild(instance)

                    # Избегаем падения на объектах без родителей — берем правильную арматуру
                    armature = utils.get_armature_for_object(object_)
                    if armature:
                        extra = self._create_physic_proxy_for_bone(armature, bone)
                        if extra is not None:
                            node.appendChild(extra)

            elif utils.is_physic_bone(bone):
                bone_geometry = utils.get_bone_geometry(bone)
                if fakebone is not None:
                    self._write_transforms(fakebone, node)

            parent_node.appendChild(node)

            if bone.children:
                self._write_bone_list(bone.children, object_, node, group)

    def _create_bone_instance(self, bone_geometry, geometry_name):
        """Binds structural mesh nodes onto skeletal bones."""
        instance = self._doc.createElement("instance_geometry")
        instance.setAttribute("url", f"#{geometry_name}")
        bm = self._doc.createElement("bind_material")
        tc = self._doc.createElement("technique_common")

        for mat in bone_geometry.material_slots:
            im = self._doc.createElement("instance_material")
            im.setAttribute("symbol", mat.name)
            im.setAttribute("target", f"#{mat.name}")

            bvi = self._doc.createElement("bind_vertex_input")
            bvi.setAttribute("semantic", "UVMap")
            bvi.setAttribute("input_semantic", "TEXCOORD")
            bvi.setAttribute("input_set", "0")
            im.appendChild(bvi)
            tc.appendChild(im)

        bm.appendChild(tc)
        instance.appendChild(bm)
        return instance

    def _create_physic_proxy_for_bone(self, object_, bone):
        """Creates standard profiles mapping joint limits parameters."""
        extra = None
        try:
            bone_phys = object_.pose.bones[bone.name]["phys_proxy"]
            bcPrint(f"Bone proxy configured: {bone.name} -> {bone_phys}")

            extra = self._doc.createElement("extra")
            techcry = self._doc.createElement("technique")
            techcry.setAttribute("profile", "CryEngine")
            prop2 = self._doc.createElement("properties")

            cryprops = self._doc.createTextNode(bone_phys)
            prop2.appendChild(cryprops)
            techcry.appendChild(prop2)
            extra.appendChild(techcry)
        except KeyError:
            pass

        return extra

    def _create_instance(self, group, object_):
        """Binds mesh layouts either as static helpers or rigged controllers."""
        armature = utils.get_armature_for_object(object_)
        node_type = utils.get_node_type(group)
        instance = None

        if armature and node_type in ("chr", "skin"):
            instance = self._doc.createElement("instance_controller")
            instance.setAttribute("url", f"#{armature.name}_{object_.name}")
        elif object_.name[:6] != "_joint" and object_.type == "MESH":
            instance = self._doc.createElement("instance_geometry")
            instance.setAttribute("url", f"#{utils.get_geometry_name(group, object_)}")

        if instance is not None:
            bind_material = self._create_bind_material(object_)
            instance.appendChild(bind_material)
            return instance

    def _create_cryengine_extra(self, node):
        """Generates standard CryEngine-specific XML file type tags."""
        extra = self._doc.createElement("extra")
        technique = self._doc.createElement("technique")
        technique.setAttribute("profile", "CryEngine")
        properties = self._doc.createElement("properties")

        ALLOWED_NODE_TYPES = ("cgf", "cga", "chr", "skin")
        if utils.is_export_node(node):
            node_type = utils.get_node_type(node)
            if node_type in ALLOWED_NODE_TYPES:
                prop = self._doc.createTextNode(f"fileType={node_type}")
                properties.appendChild(prop)

        technique.appendChild(properties)
        extra.appendChild(technique)
        return extra

    def _create_user_defined_property(self, object_):
        """Injects custom parameters (UDP) directly to COLLADA visual node tags."""
        extra = self._doc.createElement("extra")
        technique = self._doc.createElement("technique")
        technique.setAttribute("profile", "CryEngine")
        properties = self._doc.createElement("properties")

        udp_list = ""
        for key in object_.keys():
            if udp.is_user_defined_property(key):
                udp_list = f"{udp_list}{key}={object_[key]}\n"

        if udp_list:
            node_props = self._doc.createTextNode(udp_list)
            properties.appendChild(node_props)
            technique.appendChild(properties)
            extra.appendChild(technique)
            return extra

        return None

    def _create_helper_for_dummy(self, object_):
        """Assembles dummy spatial tracking properties."""
        extra = self._doc.createElement("extra")
        technique = self._doc.createElement("technique")
        technique.setAttribute("profile", "CryEngine")
        properties = self._doc.createElement("properties")

        prop_node = self._doc.createTextNode("helper_type=dummy")
        properties.appendChild(prop_node)
        technique.appendChild(properties)
        extra.appendChild(technique)
        return extra

    def _create_ik_properties(self, bone, object_):
        """Formats IK lock, limits, tension, and damping attributes (safe for unparented meshes and legacy RCs)."""
        if getattr(self._config, "legacy_rc", False):
            return ""

        props = ""
        if utils.is_physic_bone(bone):
            armature = utils.get_armature_for_object(object_)
            if not armature:
                return ""

            # Physic bones typically have a name ending in "_Phys"
            pose_bone_name = bone.name
            if pose_bone_name.endswith("_Phys"):
                pose_bone_name = pose_bone_name[:-5]

            pose_bone = armature.pose.bones.get(pose_bone_name)
            if pose_bone is None:
                return ""

            x_ik, y_ik, z_ik = udp.get_bone_ik_max_min(pose_bone)
            damping, spring, spring_tension = udp.get_bone_ik_properties(pose_bone)

            props = utils.join(
                x_ik,
                f"_xdamping={damping[1]}",
                f"_xspringangle={spring[1]}",
                f"_xspringtension={spring_tension[1]}",
                y_ik,
                f"_ydamping={damping[0]}",
                f"_yspringangle={spring[0]}",
                f"_yspringtension={spring_tension[0]}",
                z_ik,
                f"_zdamping={damping[2]}",
                f"_zspringangle={spring[2]}",
                f"_zspringtension={spring_tension[2]}",
            )

        return props


def save(config):
    """Execution proxy validating paths and invoking exporter."""
    if not config.disable_rc and not os.path.isfile(config.rc_path):
        raise exceptions.NoRcSelectedException()

    exporter = CrytekDaeExporter(config)
    exporter.export()
