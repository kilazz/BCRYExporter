# ------------------------------------------------------------------------------
# Name:        operators/material_ops.py
# Purpose:     All operator classes related to material setup and physical properties
# ------------------------------------------------------------------------------

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

# Modular package imports
from ..core.config import Configuration, VERSION
from ..core.logger import bcPrint
from ..core import exceptions
from ..engine import constants
from .. import utils

# Import our compiled material utility functions from the exporter module
from ..exporter import materials as material_utils


class BCRY_OT_add_material(bpy.types.Operator):
    """Add material to node"""

    bl_label = "Add Material to Node"
    bl_idname = "bcry.add_cry_material"
    bl_options = {"REGISTER", "UNDO"}

    material_name: StringProperty(name="Material")

    physics_type: EnumProperty(
        name="Physics",
        items=(
            ("physDefault", "Default", constants.DESCRIPTIONS["physDefault"]),
            ("physProxyNoDraw", "Proxy", constants.DESCRIPTIONS["physProxyNoDraw"]),
            ("physNoCollide", "Collide", constants.DESCRIPTIONS["physNoCollide"]),
            ("physObstruct", "Obstruct", constants.DESCRIPTIONS["physObstruct"]),
            ("physNone", "None", constants.DESCRIPTIONS["physNone"]),
        ),
        default="physNone",
    )

    errorReport = None
    exportNode = None

    def execute(self, context):
        if bpy.context.selected_objects:
            # Get new index for material in this group (export node)
            # CryEngine material slot starts with 01 instead of 00 (matches 3ds Max indexes)
            index = (
                len(material_utils.get_materials_per_group(self.exportNode.name)) + 1
            )

            # Generate new material with standard physical naming structure
            material = bpy.data.materials.new(
                f"{utils.get_node_name(self.exportNode)}__{index:02d}__{self.material_name}__{self.physics_type}"
            )

            for _object in bpy.context.selected_objects:
                _object.data.materials.append(material)
                message = f"Assigned material: {material.name} to {_object.name}"
                bcPrint(message)
        else:
            self.report({"ERROR"}, "No Objects Selected")
            return {"CANCELLED"}

        self.report({"INFO"}, "Assigned material successfully.")
        return {"FINISHED"}

    def invoke(self, context, event):
        cry_node_report = "Please select at least one object inside a Cry Export node"
        if not bpy.context.selected_objects:
            self.errorReport = cry_node_report
        else:
            self.exportNode = None
            for _object in bpy.context.selected_objects:
                if self.errorReport is not None:
                    break
                # Find the export node the object is in, and verify singular parent node bounds
                for collection in _object.users_collection:
                    if utils.is_export_node(collection):
                        if self.exportNode is None:
                            self.exportNode = collection
                        elif self.exportNode != collection:
                            self.errorReport = "Objects are in multiple Cry Export nodes. Operation cancelled to avoid corruption."
                            break
            if self.exportNode is None:
                self.errorReport = cry_node_report
            else:
                if self.errorReport is None:
                    return context.window_manager.invoke_props_dialog(self)

        self.report({"ERROR"}, self.errorReport)
        return {"CANCELLED"}


class BCRY_OT_add_material_properties(bpy.types.Operator):
    """Add BCRY Exporter material properties to all materials in the selected export node.
    Will not replace phys type if already exists, but will update the index.
    """

    bl_label = "Add BCRY Exporter material properties to materials"
    bl_idname = "bcry.add_material_properties"

    material_phys: EnumProperty(
        name="Physical Proxy",
        items=(
            ("physDefault", "Default", constants.DESCRIPTIONS["physDefault"]),
            (
                "physProxyNoDraw",
                "Physical Proxy",
                constants.DESCRIPTIONS["physProxyNoDraw"],
            ),
            ("physNoCollide", "No Collide", constants.DESCRIPTIONS["physNoCollide"]),
            ("physObstruct", "Obstruct", constants.DESCRIPTIONS["physObstruct"]),
            ("physNone", "None", constants.DESCRIPTIONS["physNone"]),
        ),
        default="physNone",
    )

    object_ = None
    errorReport = None
    exportNode = None
    material_name = None

    def execute(self, context):
        if self.errorReport is not None:
            return {"FINISHED"}

        # Fetch active physical parameters across all registry settings
        physics_properties = material_utils.get_material_physics()
        material_counter = material_utils.get_material_counter()

        handled_sub_mat_names = {}
        for obj in self.exportNode.objects:
            for slot in obj.material_slots:
                if not slot.material:
                    continue
                material_old_name = slot.material.name
                material_old_name_no_props = material_utils.remove_bcry_properties(
                    material_old_name
                )

                if handled_sub_mat_names.get(material_old_name_no_props) is None:
                    material_counter[self.exportNode.name] += 1
                    handled_sub_mat_names[material_old_name_no_props] = 1

                    # Load physical descriptors or fallback to active choice
                    if physics_properties.get(material_old_name_no_props):
                        physics = physics_properties[material_old_name_no_props]
                    else:
                        physics = self.material_phys
                        message = f"Assigned physics '{physics}' to material '{material_old_name}'"
                        self.report({"INFO"}, message)
                        bcPrint(message)

                    # Update slot name mapping
                    slot.material.name = f"{self.material_name}__{material_counter[self.exportNode.name]:02d}__{utils.replace_invalid_rc_characters(material_old_name_no_props)}__{physics}"
                    message = f"Renamed {material_old_name} -> {slot.material.name}"
                    bcPrint(message)
                else:
                    handled_sub_mat_names[material_old_name_no_props] += 1

        return {"FINISHED"}

    def invoke(self, context, event):
        cry_node_report = (
            "Please select an object in a Cry Export node. "
            "If you have not created one yet, please create it via 'Add Export Node'."
        )

        self.object_ = bpy.context.active_object
        if self.object_ is None:
            self.errorReport = cry_node_report
        else:
            self.exportNode = None
            for collection in self.object_.users_collection:
                if utils.is_export_node(collection):
                    if self.exportNode is None:
                        self.exportNode = collection
                        self.material_name = utils.get_node_name(collection)
                    else:
                        self.errorReport = "Object is in multiple Cry Export nodes. Operation cancelled to avoid corruption."
                        break
            if self.exportNode is None:
                self.errorReport = cry_node_report
            else:
                if self.errorReport is None:
                    return context.window_manager.invoke_props_dialog(self)

        self.report({"ERROR"}, self.errorReport)
        return {"CANCELLED"}


class BCRY_OT_discard_material_properties(bpy.types.Operator):
    """Removes BCRY Exporter properties from active material on active object in export node."""

    bl_label = "Remove BCRY Exporter properties from material names"
    bl_idname = "bcry.discard_material_properties"

    def execute(self, context):
        active_mat = context.active_object.active_material
        if not active_mat:
            self.report({"ERROR"}, "No active material slot found on object.")
            return {"CANCELLED"}

        new_name = material_utils.remove_bcry_properties(active_mat.name)
        if new_name is not None:
            active_mat.name = new_name
            message = "Removed BCry Exporter properties from material names"
            self.report({"INFO"}, message)
        else:
            message = "Remove properties failed"
            self.report({"ERROR"}, message)

        bcPrint(message)
        return {"FINISHED"}


class BCRY_OT_generate_materials(bpy.types.Operator, ExportHelper):
    """Generate material files for CryEngine."""

    bl_label = "Generate Materials"
    bl_idname = "bcry.generate_materials"
    filename_ext = ".mtl"
    filter_glob: StringProperty(default="*.mtl", options={"HIDDEN"})

    export_selected_nodes: BoolProperty(
        name="Just Selected Nodes",
        description="Generate material files just for selected nodes.",
        default=False,
    )
    convert_textures: BoolProperty(
        name="Convert Textures",
        description="Converts source textures to DDS while generating materials.",
        default=False,
    )

    merge_all_nodes = True
    make_layer = False

    class Config:
        def __init__(self, config):
            attributes = ("filepath", "export_selected_nodes", "convert_textures")
            for attribute in attributes:
                setattr(self, attribute, getattr(config, attribute))

            self.bcry_version = VERSION
            self.rc_path = Configuration.rc_path
            self.texture_rc_path = Configuration.texture_rc_path
            self.game_dir = Configuration.game_dir

    def execute(self, context):
        bcPrint(Configuration.rc_path, "debug")
        try:
            config = BCRY_OT_generate_materials.Config(config=self)
            material_utils.generate_mtl_files(config)
        except exceptions.BCryException as exception:
            bcPrint(exception.what(), "error")
            bpy.ops.bcry.display_error("INVOKE_DEFAULT", message=exception.what())

        return {"FINISHED"}

    def invoke(self, context, event):
        if not Configuration.configured():
            self.report({"ERROR"}, "Resource Compiler path not set.")
            return {"FINISHED"}
        if not utils.get_export_nodes():
            self.report({"ERROR"}, "No active CryExportNode groups found in scene.")
            return {"FINISHED"}

        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        box = col.box()
        box.label(text="Generate Materials", icon="MATERIAL")
        box.prop(self, "export_selected_nodes")
        box.prop(self, "convert_textures")


# ------------------------------------------------------------------------------
# Direct Native Context Menu Physical Assignment Actions
# ------------------------------------------------------------------------------


class BCRY_OT_set_material_phys_default(bpy.types.Operator):
    """The render geometry is used as physics proxy. This\
    is expensive for complex objects, so use this only for simple objects\
    like cubes or if you really need to fully physicalize an object."""

    bl_label = "__physDefault"
    bl_idname = "bcry.set_phys_default"

    def execute(self, context):
        material_name = context.active_object.active_material.name
        message = f"{material_name} material physic has been set to physDefault"
        self.report({"INFO"}, message)
        bcPrint(message)
        return material_utils.set_material_physic(self, context, self.bl_label)


class BCRY_OT_set_material_phys_proxy_no_draw(bpy.types.Operator):
    """Mesh is used exclusively for collision detection and is not rendered."""

    bl_label = "__physProxyNoDraw"
    bl_idname = "bcry.set_phys_proxy_no_draw"

    def execute(self, context):
        material_name = context.active_object.active_material.name
        message = f"{material_name} material physic has been set to physProxyNoDraw"
        self.report({"INFO"}, message)
        bcPrint(message)
        return material_utils.set_material_physic(self, context, self.bl_label)


class BCRY_OT_set_material_phys_none(bpy.types.Operator):
    """The render geometry have no physic just render it."""

    bl_label = "__physNone"
    bl_idname = "bcry.set_phys_none"

    def execute(self, context):
        material_name = context.active_object.active_material.name
        message = f"{material_name} material physic has been set to physNone"
        self.report({"INFO"}, message)
        bcPrint(message)
        return material_utils.set_material_physic(self, context, self.bl_label)


class BCRY_OT_set_material_phys_obstruct(bpy.types.Operator):
    """Used for Soft Cover to block AI view (i.e. on dense foliage)."""

    bl_label = "__physObstruct"
    bl_idname = "bcry.set_phys_obstruct"

    def execute(self, context):
        material_name = context.active_object.active_material.name
        message = f"{material_name} material physic has been set to physObstruct"
        self.report({"INFO"}, message)
        bcPrint(message)
        return material_utils.set_material_physic(self, context, self.bl_label)


class BCRY_OT_set_material_phys_no_collide(bpy.types.Operator):
    """Special purpose proxy which is used by the engine\
    to detect player interaction (e.g. for vegetation touch bending)."""

    bl_label = "__physNoCollide"
    bl_idname = "bcry.set_phys_no_collide"

    def execute(self, context):
        material_name = context.active_object.active_material.name
        message = f"{material_name} material physic has been set to physNoCollide"
        self.report({"INFO"}, message)
        bcPrint(message)
        return material_utils.set_material_physic(self, context, self.bl_label)


# Expose classes to operators/__init__.py dynamically
classes = (
    BCRY_OT_add_material,
    BCRY_OT_add_material_properties,
    BCRY_OT_discard_material_properties,
    BCRY_OT_generate_materials,
    BCRY_OT_set_material_phys_default,
    BCRY_OT_set_material_phys_proxy_no_draw,
    BCRY_OT_set_material_phys_none,
    BCRY_OT_set_material_phys_obstruct,
    BCRY_OT_set_material_phys_no_collide,
)
