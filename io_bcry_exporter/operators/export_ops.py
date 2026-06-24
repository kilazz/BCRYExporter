# ------------------------------------------------------------------------------
# Name:        operators/export_ops.py
# Purpose:     All operator classes related to configuration and export actions
# ------------------------------------------------------------------------------

import os
import os.path
import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

# Modular package imports
from ..core import exceptions
from ..core.config import Configuration, VERSION
from ..core.logger import bcPrint
from ..engine import constants
from .. import utils

# Import the actual exporters under legacy aliases to maintain exact compatibility
from ..exporter import dae_geometry as export
from ..exporter import dae_animation as export_animations


class PathSelectTemplate(ExportHelper):
    """Abstract template helper to handle directory and file picker transactions."""

    check_existing = True

    def execute(self, context):
        self.process(self.filepath)
        Configuration.save()
        return {"FINISHED"}


class BCRY_OT_find_rc(bpy.types.Operator, PathSelectTemplate):
    """Select the Resource Compiler executable (rc.exe)"""

    bl_label = "Find The Resource Compiler"
    bl_idname = "bcry.find_rc"
    filename_ext = ".exe"

    def process(self, filepath):
        Configuration.rc_path = filepath
        bcPrint(f"Found Resource Compiler at {Configuration.rc_path!r}.", "debug")

    def invoke(self, context, event):
        self.filepath = Configuration.rc_path
        return ExportHelper.invoke(self, context, event)


class BCRY_OT_find_rc_for_texture_conversion(bpy.types.Operator, PathSelectTemplate):
    """Provide a path to a legacy CryEngine RC executable if current RC is 3.4.5+"""

    bl_label = "Find the Resource Compiler for Texture Conversion"
    bl_idname = "bcry.find_rc_for_texture_conversion"
    filename_ext = ".exe"

    def process(self, filepath):
        Configuration.texture_rc_path = filepath
        bcPrint(f"Found Texture RC at {Configuration.texture_rc_path!r}.", "debug")

    def invoke(self, context, event):
        self.filepath = Configuration.texture_rc_path
        return ExportHelper.invoke(self, context, event)


class BCRY_OT_select_game_directory(bpy.types.Operator, PathSelectTemplate):
    """Configures the game directory, which generates relative texture path mappings"""

    bl_label = "Select Game Directory"
    bl_idname = "bcry.select_game_dir"
    filename_ext = ""

    def process(self, filepath):
        if not os.path.isdir(filepath):
            filepath = os.path.dirname(filepath)
            if not os.path.isdir(filepath):
                raise Exception("The selected directory is invalid!")

        Configuration.game_dir = filepath
        bcPrint(f"Game directory configured: {Configuration.game_dir!r}.", "debug")

    def invoke(self, context, event):
        self.filepath = Configuration.game_dir
        return ExportHelper.invoke(self, context, event)


class BCRY_OT_save_bcry_configuration(bpy.types.Operator):
    """Saves active configuration parameters directly to bcry.json"""

    bl_label = "Save Config File"
    bl_idname = "bcry.config_save"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        Configuration.save()
        return {"FINISHED"}


class BCRY_OT_add_cry_export_node(bpy.types.Operator):
    """Add selected objects to an existing or new CryExportNode"""

    bl_label = "Add Export Node"
    bl_idname = "bcry.add_cry_export_node"
    bl_options = {"REGISTER", "UNDO"}

    node_type: EnumProperty(
        name="Type",
        items=(
            ("cgf", "CGF", "Static Geometry"),
            ("cga", "CGA", "Animated Geometry"),
            ("chr", "CHR", "Character"),
            ("skin", "SKIN", "Skinned Render Mesh"),
        ),
        default="cgf",
    )
    node_name: StringProperty(name="Name")

    def execute(self, context):
        bpy.ops.object.mode_set(mode="OBJECT")
        if bpy.context.selected_objects:
            scene = bpy.context.scene
            node_name = f"{self.node_name}.{self.node_type}"
            export_node_collection = bpy.data.collections.get("cry_export_nodes")

            # Initialize parent collection if missing
            if export_node_collection is None:
                export_node_collection = bpy.data.collections.new("cry_export_nodes")
                scene.collection.children.link(export_node_collection)

            collection = bpy.data.collections.get(node_name)
            if collection is None:
                collection = bpy.data.collections.new(node_name)
                export_node_collection.children.link(collection)

            for obj in bpy.context.selected_objects:
                if obj.name not in collection.objects:
                    if len(obj.users_collection) > 0:
                        for c in list(obj.users_collection):
                            c.objects.unlink(obj)
                    collection.objects.link(obj)
            message = f"Added objects to {node_name}"
        else:
            message = "No Objects Selected"

        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, event):
        object_ = context.active_object
        if not object_:
            self.report({"ERROR"}, "No active object selected!")
            return {"CANCELLED"}
        if object_.type not in ("MESH", "EMPTY"):
            self.report({"ERROR"}, "Selected object must be a mesh or helper empty!")
            return {"CANCELLED"}

        self.node_name = object_.name
        self.node_type = "cgf"

        if object_.parent and object_.parent.type == "ARMATURE":
            if len(object_.data.vertices) <= 4:
                self.node_type = "chr"
                self.node_name = object_.parent.name
            else:
                self.node_type = "skin"
        elif object_.animation_data:
            self.node_type = "cga"

        return context.window_manager.invoke_props_dialog(self)


class BCRY_OT_add_cry_animation_node(bpy.types.Operator):
    """Add animation node to selected armature or object"""

    bl_label = "Add Animation Node"
    bl_idname = "bcry.add_cry_animation_node"
    bl_options = {"REGISTER", "UNDO"}

    node_type: EnumProperty(
        name="Type",
        items=(
            ("anm", "ANM", "Geometry Animation"),
            ("i_caf", "I_CAF", "Character Animation"),
        ),
        default="i_caf",
    )
    node_name: StringProperty(name="Animation Name")
    mode: EnumProperty(
        name="Mode",
        items=(("Manual", "Manual", ""), ("Auto", "Auto", "")),
        default="Manual",
    )
    range_type: EnumProperty(
        name="Range Type",
        items=(
            ("Timeline", "Timeline Editor", constants.DESCRIPTIONS["range_timeline"]),
            ("Values", "Limit with Values", constants.DESCRIPTIONS["range_values"]),
            ("Markers", "Limit with Markers", constants.DESCRIPTIONS["range_markers"]),
        ),
        default="Timeline",
    )
    node_start: IntProperty(name="Start Frame")
    node_end: IntProperty(name="End Frame")
    start_m_name: StringProperty(name="Marker Start Name")
    end_m_name: StringProperty(name="Marker End Name")
    start_m_name_auto: StringProperty(name="Start")
    end_m_name_auto: StringProperty(name="End")

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "node_type")

        if self.node_type == "i_caf":
            col.label(text="Mode:")
            row = col.row()
            row.prop(self, "mode", expand=True)
        col.separator()

        if self.mode == "Manual":
            col.prop(self, "node_name")
        col.separator()

        if self.mode == "Manual" or self.node_type == "anm":
            col.label(text="Range Type:")
            col.prop(self, "range_type", expand=True)
            col.separator()
            col.separator()

            col.label(text="Animation Range Values:")
            col.prop(self, "node_start")
            col.prop(self, "node_end")
            col.separator()
            col.separator()

            col.label(text="Animation Range Markers:")
            col.prop(self, "start_m_name")
            col.prop(self, "end_m_name")

        if self.mode == "Auto":
            col.label(text="Marker Name Ends:")
            col.prop(self, "start_m_name_auto")
            col.prop(self, "end_m_name_auto")

    def execute(self, context):
        object_ = bpy.context.active_object
        scene = context.scene
        if object_:
            if self.mode == "Auto":
                self.__auto(object_, scene)
            else:
                self.__manual(object_, scene)
            message = "Added Export Animation Node"
        else:
            message = "Active Armature not found! Please select an Armature."

        self.report({"INFO"}, message)
        return {"FINISHED"}

    def __manual(self, object_, scene):
        node_start = None
        node_end = None

        start_name = f"{self.node_name}_Start"
        end_name = f"{self.node_name}_End"

        if self.range_type == "Values":
            node_start = self.node_start
            node_end = self.node_end
            object_[start_name] = node_start
            object_[end_name] = node_end

        elif self.range_type == "Markers":
            node_start = self.start_m_name
            node_end = self.end_m_name

            tm = bpy.context.scene.timeline_markers
            if tm.find(self.start_m_name) == -1:
                tm.new(name=self.start_m_name, frame=self.node_start)
            if tm.find(self.end_m_name) == -1:
                tm.new(name=self.end_m_name, frame=self.node_end)

            object_[start_name] = node_start
            object_[end_name] = node_end

        export_node = bpy.data.collections.get("cry_export_nodes")
        if export_node is None:
            export_node = bpy.data.collections.new("cry_export_nodes")
            scene.collection.children.link(export_node)

        node_name = f"{self.node_name}.{self.node_type}"
        collection = bpy.data.collections.get(node_name)
        if collection is None:
            collection = bpy.data.collections.new(node_name)
            export_node.children.link(collection)
            collection.objects.link(object_)
        else:
            for obj in bpy.context.selected_objects:
                if obj.name not in collection.objects:
                    collection.objects.link(obj)

    def __auto(self, object_, scene):
        node_start = None
        node_end = None
        node_name = None
        marker_groups = []
        self.node_type = "i_caf"
        tm = bpy.context.scene.timeline_markers

        for marker in tm.values():
            start_marker = None
            end_marker = None
            if not marker.name.endswith(self.end_m_name_auto):
                if self.start_m_name_auto != "":
                    if marker.name.endswith(self.start_m_name_auto):
                        start_marker = marker
                        node_name = marker.name[: -len(self.start_m_name_auto)]
                        end_marker = tm.get(f"{node_name}{self.end_m_name_auto}")
                else:
                    node_name = marker.name
                    start_marker = marker
                    end_marker = tm.get(f"{marker.name}{self.end_m_name_auto}")

                if start_marker and end_marker:
                    marker_groups.append(
                        (start_marker.frame, end_marker.frame, node_name)
                    )

        export_node = bpy.data.collections.get("cry_export_nodes")
        if export_node is None:
            export_node = bpy.data.collections.new("cry_export_nodes")
            scene.collection.children.link(export_node)

        for marker in marker_groups:
            node_start = marker[0]
            node_end = marker[1]
            node_name = marker[2]

            start_name = f"{node_name}_Start"
            end_name = f"{node_name}_End"

            object_[start_name] = node_start
            object_[end_name] = node_end

            node_name = f"{node_name}.{self.node_type}"
            collection = bpy.data.collections.get(node_name)
            if collection is None:
                collection = bpy.data.collections.new(node_name)
                export_node.children.link(collection)
                collection.objects.link(object_)
            else:
                for obj in bpy.context.selected_objects:
                    if obj.name not in collection.objects:
                        collection.objects.link(obj)

    def invoke(self, context, event):
        obj = context.active_object
        if not obj:
            self.report({"ERROR"}, "Please select an Armature or Object.")
            return {"CANCELLED"}

        self.node_type = "i_caf" if obj.type == "ARMATURE" else "anm"

        scene = context.scene
        self.node_start = scene.frame_start
        self.node_end = scene.frame_end

        self.start_m_name_auto = ""
        self.end_m_name_auto = "_E"

        tm = scene.timeline_markers
        for marker in tm:
            if marker.select:
                self.start_m_name = marker.name
                self.end_m_name = f"{marker.name}_E"
                self.node_start = marker.frame
                if tm.get(self.end_m_name):
                    self.node_end = tm[self.end_m_name].frame
                self.node_name = marker.name
                break

        return context.window_manager.invoke_props_dialog(self)


class BCRY_OT_selected_to_cry_export_nodes(bpy.types.Operator):
    """Add selected objects to individual CryExportNodes."""

    bl_label = "Nodes from Object Names"
    bl_idname = "bcry.selected_to_cry_export_nodes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = bpy.context.selected_objects

        export_node_collection = bpy.data.collections.get("cry_export_nodes")
        if export_node_collection is None:
            export_node_collection = bpy.data.collections.new("cry_export_nodes")
            bpy.context.scene.collection.children.link(export_node_collection)

        for object_ in selected:
            name = f"{object_.name}.cgf"
            if len(object_.users_collection) > 0:
                for collection in list(object_.users_collection):
                    collection.objects.unlink(object_)

            new_collection = bpy.data.collections.new(name)
            new_collection.objects.link(object_)
            export_node_collection.children.link(new_collection)

        message = "Assigned objects to custom individual nodes."
        self.report({"INFO"}, message)
        return {"FINISHED"}

    def invoke(self, context, event):
        if len(context.selected_objects) == 0:
            self.report({"ERROR"}, "Select one or more objects in OBJECT mode.")
            return {"FINISHED"}

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Confirm creation of nodes...")


class BCRY_OT_export(bpy.types.Operator, ExportHelper):
    """Execute main scene compile export pass to CryEngine."""

    bl_label = "Export to CryEngine"
    bl_idname = "bcry.export_to_game"
    filename_ext = ".dae"
    filter_glob: StringProperty(default="*.dae", options={"HIDDEN"})

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply all modifiers for objects before exporting.",
        default=True,
    )
    merge_all_nodes: BoolProperty(
        name="Merge All Nodes",
        description=constants.DESCRIPTIONS["merge_all_nodes"],
        default=False,
    )
    export_selected_nodes: BoolProperty(
        name="Export Selected Nodes",
        description="Just exports selected nodes.",
        default=False,
    )
    custom_normals: BoolProperty(
        name="Use Custom Normals",
        description="Use custom normals. Usually TRUE otherwise RC will auto generate and probably differ from Blender normals.",
        default=True,
    )
    use_f32_vertex_format: BoolProperty(
        name="Use F32 Vertex Format",
        description="Use F32 vertex format instead of default F16. (For more precise vertex positions when far from pivot. Also can be used for morphs(shape keys))",
        default=False,
    )
    eight_weights_per_vertex: BoolProperty(
        name="8 Weights Per Vertex",
        description="Force Use 8 weights per vertex instead of default 4. (CryEngine can auto detect up to 8 weights when necessary even if this is not set.)",
        default=False,
    )
    vcloth_pre_process: BoolProperty(
        name="VCloth Pre-Process",
        description="Export skin as simulating mesh for VCloth V2.",
        default=False,
    )
    generate_materials: BoolProperty(
        name="Generate Materials",
        description="Generate material files for CryEngine.",
        default=False,
    )
    convert_textures: BoolProperty(
        name="Convert Textures",
        description="Converts source textures to DDS while exporting materials.",
        default=False,
    )
    make_chrparams: BoolProperty(
        name="Make CHRPARAMS File",
        description="Create a base CHRPARAMS file for character animations.",
        default=False,
    )
    make_cdf: BoolProperty(
        name="Make CDF File",
        description="Create a base CDF file for character attachments.",
        default=False,
    )
    fix_weights: BoolProperty(
        name="Fix Weights",
        description="For use with .chr files. Generally a good idea.",
        default=False,
    )
    export_for_lumberyard: BoolProperty(
        name="Export for LumberYard",
        description="Export for LumberYard engine instead of CryEngine.",
        default=False,
    )
    legacy_rc: BoolProperty(
        name="Legacy RC (Crysis 2 / CE3)",
        description="Provides compatibility with older Resource Compilers by disabling CE5-parameters and auto-converting Bip01 underscores to spaces for Crysis 2 skeletons.",
        default=False,
    )
    make_layer: BoolProperty(
        name="Make LYR File",
        description="Makes a LYR to reassemble your scene in CryEngine.",
        default=False,
    )
    disable_rc: BoolProperty(
        name="Disable RC",
        description="Do not run the resource compiler.",
        default=False,
    )
    save_dae: BoolProperty(
        name="Save DAE File",
        description="Save the DAE file for developing purposes.",
        default=False,
    )
    save_tiffs: BoolProperty(
        name="Save TIFFs",
        description="Saves TIFF images that are generated during conversion to DDS.",
        default=False,
    )
    run_in_profiler: BoolProperty(
        name="Profile BCry Exporter",
        description="Select only if you want to profile BCry Exporter.",
        default=False,
    )

    is_animation_process = False

    class Config:
        def __init__(self, config):
            attributes = (
                "filepath",
                "apply_modifiers",
                "merge_all_nodes",
                "export_selected_nodes",
                "custom_normals",
                "use_f32_vertex_format",
                "eight_weights_per_vertex",
                "vcloth_pre_process",
                "generate_materials",
                "convert_textures",
                "make_chrparams",
                "make_cdf",
                "fix_weights",
                "export_for_lumberyard",
                "legacy_rc",
                "make_layer",
                "disable_rc",
                "save_dae",
                "save_tiffs",
                "run_in_profiler",
                "is_animation_process",
            )
            for attribute in attributes:
                setattr(self, attribute, getattr(config, attribute))

            self.bcry_version = VERSION
            self.rc_path = Configuration.rc_path
            self.texture_rc_path = Configuration.texture_rc_path
            self.game_dir = Configuration.game_dir

    def execute(self, context):
        bcPrint(Configuration.rc_path, "debug", True)

        Configuration.apply_modifiers = self.apply_modifiers
        Configuration.merge_all_nodes = self.merge_all_nodes
        Configuration.export_selected_nodes = self.export_selected_nodes
        Configuration.custom_normals = self.custom_normals
        Configuration.use_f32_vertex_format = self.use_f32_vertex_format
        Configuration.eight_weights_per_vertex = self.eight_weights_per_vertex
        Configuration.vcloth_pre_process = self.vcloth_pre_process
        Configuration.generate_materials = self.generate_materials
        Configuration.convert_textures = self.convert_textures
        Configuration.make_chrparams = self.make_chrparams
        Configuration.make_cdf = self.make_cdf
        Configuration.fix_weights = self.fix_weights
        Configuration.export_for_lumberyard = self.export_for_lumberyard
        Configuration.legacy_rc = self.legacy_rc
        Configuration.make_layer = self.make_layer
        Configuration.disable_rc = self.disable_rc
        Configuration.save_dae = self.save_dae
        Configuration.save_tiffs = self.save_tiffs
        Configuration.run_in_profiler = self.run_in_profiler
        Configuration.save()

        try:
            config = BCRY_OT_export.Config(config=self)
            if self.run_in_profiler:
                import cProfile

                cProfile.runctx(
                    "export.save(config)", {}, {"export": export, "config": config}
                )
            else:
                export.save(config)
        except exceptions.BCryException as exception:
            bcPrint(exception.what(), "error")
            bpy.ops.bcry.display_error("INVOKE_DEFAULT", message=exception.what())

        return {"FINISHED"}

    def invoke(self, context, event):
        if not Configuration.configured():
            self.report({"ERROR"}, "Resource Compiler path not set.")
            return {"FINISHED"}
        if not utils.get_export_nodes():
            self.report({"ERROR"}, "No CryExportNode groups found in scene.")
            return {"FINISHED"}

        self.apply_modifiers = Configuration.apply_modifiers
        self.merge_all_nodes = Configuration.merge_all_nodes
        self.export_selected_nodes = Configuration.export_selected_nodes
        self.custom_normals = Configuration.custom_normals
        self.use_f32_vertex_format = Configuration.use_f32_vertex_format
        self.eight_weights_per_vertex = Configuration.eight_weights_per_vertex
        self.vcloth_pre_process = Configuration.vcloth_pre_process
        self.generate_materials = Configuration.generate_materials
        self.convert_textures = Configuration.convert_textures
        self.make_chrparams = Configuration.make_chrparams
        self.make_cdf = Configuration.make_cdf
        self.fix_weights = Configuration.fix_weights
        self.export_for_lumberyard = Configuration.export_for_lumberyard
        self.legacy_rc = Configuration.legacy_rc
        self.make_layer = Configuration.make_layer
        self.disable_rc = Configuration.disable_rc
        self.save_dae = Configuration.save_dae
        self.save_tiffs = Configuration.save_tiffs
        self.run_in_profiler = Configuration.run_in_profiler

        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        box = col.box()
        box.label(text="General", icon="WORLD")
        box.prop(self, "apply_modifiers")
        box.prop(self, "merge_all_nodes")
        box.prop(self, "export_selected_nodes")
        box.prop(self, "custom_normals")
        box.prop(self, "use_f32_vertex_format")
        box.prop(self, "eight_weights_per_vertex")
        box.prop(self, "vcloth_pre_process")

        box = col.box()
        box.label(text="Material & Texture", icon="TEXTURE")
        box.prop(self, "generate_materials")
        box.prop(self, "convert_textures")

        box = col.box()
        box.label(text="Character", icon="ARMATURE_DATA")
        box.prop(self, "make_chrparams")
        box.prop(self, "make_cdf")

        box = col.box()
        box.label(text="Corrective", icon="BRUSH_DATA")
        box.prop(self, "fix_weights")

        box = col.box()
        box.label(text="LumberYard", icon="PLUGIN")
        box.prop(self, "export_for_lumberyard")

        box = col.box()
        box.label(text="Legacy Tools", icon="MODIFIER")
        box.prop(self, "legacy_rc")

        box = col.box()
        box.label(text="CryEngine Editor", icon="PLUGIN")
        box.prop(self, "make_layer")

        box = col.box()
        box.label(text="Developer Tools", icon="MODIFIER")
        box.prop(self, "disable_rc")
        box.prop(self, "save_dae")
        box.prop(self, "save_tiffs")
        box.prop(self, "run_in_profiler")


class BCRY_OT_export_animations(bpy.types.Operator, ExportHelper):
    """Export standard armature keyframe ranges to standard CryEngine track files."""

    bl_label = "Export Animations"
    bl_idname = "bcry.export_animations"
    filename_ext = ".dae"
    filter_glob: StringProperty(default="*.dae", options={"HIDDEN"})

    export_for_lumberyard: BoolProperty(
        name="Export for LumberYard",
        description="Export for LumberYard engine instead of CryEngine.",
        default=False,
    )
    disable_rc: BoolProperty(
        name="Disable RC",
        description="Do not run the resource compiler.",
        default=False,
    )
    save_dae: BoolProperty(
        name="Save DAE File",
        description="Save the DAE file for developing purposes.",
        default=False,
    )
    run_in_profiler: BoolProperty(
        name="Profile BCry Exporter",
        description="Select only if you want to profile BCry Exporter.",
        default=False,
    )
    merge_all_nodes = True
    generate_materials = False
    make_layer = False
    vcloth_pre_process = False
    is_animation_process = True

    class Config:
        def __init__(self, config):
            attributes = (
                "filepath",
                "merge_all_nodes",
                "vcloth_pre_process",
                "generate_materials",
                "export_for_lumberyard",
                "is_animation_process",
                "make_layer",
                "disable_rc",
                "save_dae",
                "run_in_profiler",
            )
            for attribute in attributes:
                setattr(self, attribute, getattr(config, attribute))

            self.bcry_version = VERSION
            self.rc_path = Configuration.rc_path
            self.texture_rc_path = Configuration.texture_rc_path
            self.game_dir = Configuration.game_dir

    def execute(self, context):
        bcPrint(Configuration.rc_path, "debug")
        try:
            config = BCRY_OT_export_animations.Config(config=self)
            if self.run_in_profiler:
                import cProfile

                cProfile.runctx(
                    "export_animations.save(config)",
                    {},
                    {"export_animations": export_animations, "config": config},
                )
            else:
                export_animations.save(config)
        except exceptions.BCryException as exception:
            bcPrint(exception.what(), "error")
            bpy.ops.bcry.display_error("INVOKE_DEFAULT", message=exception.what())

        return {"FINISHED"}

    def invoke(self, context, event):
        if not Configuration.configured():
            self.report({"ERROR"}, "Resource Compiler path not set.")
            return {"FINISHED"}
        if not utils.get_export_nodes():
            self.report({"ERROR"}, "No CryExportNode groups found in scene.")
            return {"FINISHED"}

        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        box = col.box()
        box.label(text="LumberYard", icon="PLUGIN")
        box.prop(self, "export_for_lumberyard")

        box = col.box()
        box.label(text="Developer Tools", icon="MODIFIER")
        box.prop(self, "disable_rc")
        box.prop(self, "save_dae")
        box.prop(self, "run_in_profiler")


class BCRY_OT_quick_export(bpy.types.Operator, ExportHelper):
    """Bypasses file save dialogue to export to current folder context."""

    bl_label = "Quick Export to CryEngine"
    bl_idname = "bcry.export_to_game_quick"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".dae"
    filter_glob: StringProperty(default="*.dae", options={"HIDDEN"})

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply all modifiers for objects before exporting.",
        default=True,
    )
    merge_all_nodes: BoolProperty(
        name="Merge All Nodes",
        description=constants.DESCRIPTIONS["merge_all_nodes"],
        default=False,
    )
    export_selected_nodes: BoolProperty(
        name="Export Selected Nodes",
        description="Just exports selected nodes.",
        default=False,
    )
    custom_normals: BoolProperty(
        name="Use Custom Normals",
        description="Use custom normals. Usually TRUE otherwise RC will auto generate and probably differ from Blender normals.",
        default=True,
    )
    use_f32_vertex_format: BoolProperty(
        name="Use F32 Vertex Format",
        description="Use F32 vertex format instead of default F16. (For more precise vertex positions when far from pivot. Also can be used for morphs(shape keys))",
        default=False,
    )
    eight_weights_per_vertex: BoolProperty(
        name="8 Weights Per Vertex",
        description="Force Use 8 weights per vertex instead of default 4. (CryEngine can auto detect up to 8 weights when necessary even if this is not set.)",
        default=False,
    )
    vcloth_pre_process: BoolProperty(
        name="VCloth Pre-Process",
        description="Export skin as simulating mesh for VCloth V2.",
        default=False,
    )
    generate_materials: BoolProperty(
        name="Generate Materials",
        description="Generate material files for CryEngine.",
        default=False,
    )
    convert_textures: BoolProperty(
        name="Convert Textures",
        description="Converts source textures to DDS while exporting materials.",
        default=False,
    )
    make_chrparams: BoolProperty(
        name="Make CHRPARAMS File",
        description="Create a base CHRPARAMS file for character animations.",
        default=False,
    )
    make_cdf: BoolProperty(
        name="Make CDF File",
        description="Create a base CDF file for character attachments.",
        default=False,
    )
    fix_weights: BoolProperty(
        name="Fix Weights",
        description="For use with .chr files. Generally a good idea.",
        default=False,
    )
    export_for_lumberyard: BoolProperty(
        name="Export for LumberYard",
        description="Export for LumberYard engine instead of CryEngine.",
        default=False,
    )
    legacy_rc: BoolProperty(
        name="Legacy RC (Crysis 2 / CE3)",
        description="Provides compatibility with older Resource Compilers by disabling CE5-parameters and auto-converting Bip01 underscores to spaces for Crysis 2 skeletons.",
        default=False,
    )
    make_layer: BoolProperty(
        name="Make LYR File",
        description="Makes a LYR to reassemble your scene in CryEngine.",
        default=False,
    )
    disable_rc: BoolProperty(
        name="Disable RC",
        description="Do not run the resource compiler.",
        default=False,
    )
    save_dae: BoolProperty(
        name="Save DAE File",
        description="Save the DAE file for developing purposes.",
        default=False,
    )
    save_tiffs: BoolProperty(
        name="Save TIFFs",
        description="Saves TIFF images that are generated during conversion to DDS.",
        default=False,
    )
    run_in_profiler: BoolProperty(
        name="Profile BCry Exporter",
        description="Select only if you want to profile BCry Exporter.",
        default=False,
    )

    is_animation_process = False

    class Config:
        def __init__(self, config):
            attributes = (
                "filepath",
                "apply_modifiers",
                "merge_all_nodes",
                "export_selected_nodes",
                "custom_normals",
                "use_f32_vertex_format",
                "eight_weights_per_vertex",
                "vcloth_pre_process",
                "generate_materials",
                "convert_textures",
                "make_chrparams",
                "make_cdf",
                "fix_weights",
                "export_for_lumberyard",
                "legacy_rc",
                "make_layer",
                "disable_rc",
                "save_dae",
                "save_tiffs",
                "run_in_profiler",
                "is_animation_process",
            )
            for attribute in attributes:
                setattr(self, attribute, getattr(config, attribute))

            self.bcry_version = VERSION
            self.rc_path = Configuration.rc_path
            self.texture_rc_path = Configuration.texture_rc_path
            self.game_dir = Configuration.game_dir

    def execute(self, context):
        bcPrint(Configuration.rc_path, "debug", True)
        self.filepath = bpy.path.abspath("//")

        Configuration.apply_modifiers = self.apply_modifiers
        Configuration.merge_all_nodes = self.merge_all_nodes
        Configuration.export_selected_nodes = self.export_selected_nodes
        Configuration.custom_normals = self.custom_normals
        Configuration.use_f32_vertex_format = self.use_f32_vertex_format
        Configuration.eight_weights_per_vertex = self.eight_weights_per_vertex
        Configuration.vcloth_pre_process = self.vcloth_pre_process
        Configuration.generate_materials = self.generate_materials
        Configuration.convert_textures = self.convert_textures
        Configuration.make_chrparams = self.make_chrparams
        Configuration.make_cdf = self.make_cdf
        Configuration.fix_weights = self.fix_weights
        Configuration.export_for_lumberyard = self.export_for_lumberyard
        Configuration.legacy_rc = self.legacy_rc
        Configuration.make_layer = self.make_layer
        Configuration.disable_rc = self.disable_rc
        Configuration.save_dae = self.save_dae
        Configuration.save_tiffs = self.save_tiffs
        Configuration.run_in_profiler = self.run_in_profiler
        Configuration.save()

        try:
            config = BCRY_OT_quick_export.Config(config=self)
            if self.run_in_profiler:
                import cProfile

                cProfile.runctx(
                    "export.save(config)", {}, {"export": export, "config": config}
                )
            else:
                export.save(config)
        except exceptions.BCryException as exception:
            bcPrint(exception.what(), "error")
            bpy.ops.bcry.display_error("INVOKE_DEFAULT", message=exception.what())

        return {"FINISHED"}

    def invoke(self, context, event):
        if not Configuration.configured():
            self.report({"ERROR"}, "Resource Compiler path not set.")
            return {"FINISHED"}
        if not utils.get_export_nodes():
            self.report({"ERROR"}, "No CryExportNode groups found in scene.")
            return {"FINISHED"}

        self.apply_modifiers = Configuration.apply_modifiers
        self.merge_all_nodes = Configuration.merge_all_nodes
        self.export_selected_nodes = Configuration.export_selected_nodes
        self.custom_normals = Configuration.custom_normals
        self.use_f32_vertex_format = Configuration.use_f32_vertex_format
        self.eight_weights_per_vertex = Configuration.eight_weights_per_vertex
        self.vcloth_pre_process = Configuration.vcloth_pre_process
        self.generate_materials = Configuration.generate_materials
        self.convert_textures = Configuration.convert_textures
        self.make_chrparams = Configuration.make_chrparams
        self.make_cdf = Configuration.make_cdf
        self.fix_weights = Configuration.fix_weights
        self.export_for_lumberyard = Configuration.export_for_lumberyard
        self.legacy_rc = Configuration.legacy_rc
        self.make_layer = Configuration.make_layer
        self.disable_rc = Configuration.disable_rc
        self.save_dae = Configuration.save_dae
        self.save_tiffs = Configuration.save_tiffs
        self.run_in_profiler = Configuration.run_in_profiler

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        box = col.box()
        box.label(text="General", icon="WORLD")
        box.prop(self, "apply_modifiers")
        box.prop(self, "merge_all_nodes")
        box.prop(self, "export_selected_nodes")
        box.prop(self, "custom_normals")
        box.prop(self, "use_f32_vertex_format")
        box.prop(self, "eight_weights_per_vertex")
        box.prop(self, "vcloth_pre_process")

        box = col.box()
        box.label(text="Material & Texture", icon="TEXTURE")
        box.prop(self, "generate_materials")
        box.prop(self, "convert_textures")

        box = col.box()
        box.label(text="Character", icon="ARMATURE_DATA")
        box.prop(self, "make_chrparams")
        box.prop(self, "make_cdf")

        box = col.box()
        box.label(text="Corrective", icon="BRUSH_DATA")
        box.prop(self, "fix_weights")

        box = col.box()
        box.label(text="LumberYard", icon="PLUGIN")
        box.prop(self, "export_for_lumberyard")

        box = col.box()
        box.label(text="Legacy Tools", icon="MODIFIER")
        box.prop(self, "legacy_rc")

        box = col.box()
        box.label(text="CryEngine Editor", icon="PLUGIN")
        box.prop(self, "make_layer")

        box = col.box()
        box.label(text="Developer Tools", icon="MODIFIER")
        box.prop(self, "disable_rc")
        box.prop(self, "save_dae")
        box.prop(self, "save_tiffs")
        box.prop(self, "run_in_profiler")


class BCRY_OT_error_handler(bpy.types.Operator):
    """Blender UI dialog to show custom BCRY errors inside standard popups."""

    bl_label = "Error:"
    bl_idname = "bcry.display_error"
    message: bpy.props.StringProperty()

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text=self.bl_label, icon="ERROR")
        col.split()
        for line in self.message.splitlines():
            row = col.split()
            row.label(text=line)
        col.split()
        col.split(0.2)


# Expose classes to operators/__init__.py dynamically
classes = (
    BCRY_OT_find_rc,
    BCRY_OT_find_rc_for_texture_conversion,
    BCRY_OT_select_game_directory,
    BCRY_OT_save_bcry_configuration,
    BCRY_OT_add_cry_export_node,
    BCRY_OT_add_cry_animation_node,
    BCRY_OT_selected_to_cry_export_nodes,
    BCRY_OT_export,
    BCRY_OT_export_animations,
    BCRY_OT_quick_export,
    BCRY_OT_error_handler,
)
