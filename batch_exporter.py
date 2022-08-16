# Copyright 2022 by Hextant Studios. https://HextantStudios.com
# This work is licensed under GNU General Public License Version 3.
# License: https://download.blender.org/release/GPL3-license.txt

import os, bpy
from pathlib import Path
from mathutils import Vector
from bpy.props import BoolProperty, StringProperty, EnumProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup

#
# Settings
#

# Force the export directory setting to use relative paths to the original Blender file.
_use_relative_paths: bool = True

#
# Enums
#

# Supported batch export formats.
# Note: Then enum (first) value must match the name of the bpy.ops.export_scene operator.
BatchExportFormatType = [
    ("gltf", "glTF", ""),
    ("fbx", "FBX", ""),
]

#
# Functions
#

# Returns true if the specified object and are its parents are batch exported.
def is_batch_exported(object) -> bool:
    if getattr(object, 'batch_export', True):
        return object.parent is None or is_batch_exported(object.parent)
    return False

# Deselect all objects in the specified view layer from that view layer.
def deselect_all(view_layer):
    for selected_object in view_layer.objects.selected.values():
        selected_object.select_set(False, view_layer = view_layer)

# Select the specified object and children that do not have 'batch_export' set to False. 
# Note: This assumes all objects were previously deselected.
def select_exportable(object):
    if object.batch_export:
        # Recurse into children and then select this object.
        for child in object.children:
            select_exportable(child)
        object.select_set(True)

# Returns the name (without the extension) of the current file.
def get_filename() -> str:
    return Path(bpy.data.filepath).stem

# Returns true if the batch_export_directory has been assigned and is valid.
def is_export_directory_valid(context) -> bool:
    export_directory = context.scene.batch_export_preferences.directory
    return os.path.isdir(bpy.path.abspath(export_directory))

# Returns '...\A\B\' from the full export directory for display.
def get_truncated_directory(export_directory) -> str:    
    indices = [i for i,c in enumerate(export_directory) if c==os.path.sep]
    if len(indices) < 4: return export_directory
    return "..." + export_directory[indices[-4]:]

# Converts a set of preferences (PropertyGroup) to a dictionary.
def to_dict( preferences : PropertyGroup ):
    return {property:getattr( preferences, property) for property in preferences.__annotations__}

# Exports a list of root objects (and exportable children) to individual files.
def export(context, preferences, objects, report=None) -> bool:
    if not report: report = lambda type, msg : print(type.pop() + ": " + msg)
    scene = context.scene
    
    # Get the export directory and verify it exists.
    export_directory = bpy.path.abspath(preferences.directory)
    if not os.path.isdir(export_directory):
        report({'ERROR'}, f"Export directory not valid: '{export_directory}'")
        return False

    # Verify the built-in exporter is enabled.
    export_format = preferences.format_type
    try:
        export_op = getattr(bpy.ops.export_scene, export_format)
    except Exception:
        report({'ERROR'}, f"Built-in {export_format} Import/Export add-on is not enabled!")
        raise

    # Verify there were objects to export.
    if not objects:
        report({'WARNING'}, "No valid objects to export!")
        return True

    # Verify objects are not children.
    child_objects = [object for object in objects if object.parent is not None]
    if child_objects:
        report({'ERROR'}, "Child objects may not be exported: " + 
            ", ".join([child.name for child in child_objects]))
        return False

    # Verify objects are not set to export=False.
    excluded_objects = [object for object in objects if not object.batch_export]
    if excluded_objects:
        report({'ERROR'}, "Attempting to export object excluded from export: " + 
            ", ".join([object.name for object in excluded_objects]))
        return False

    # Store the active object and selection for the current view layer.
    view_layer = context.view_layer
    active_object = view_layer.objects.active
    selection = view_layer.objects.selected.values()
    
    # Track successfully exported objects.
    exported_objects = []

    try:
        # Set the active object to none. This exits Edit mode. Restoring the active_object
        # before exiting below will restore its previous mode. It's possible that
        # this should call bpy.ops.object.mode_set(mode='OBJECT') instead, but there is a bug
        # with trying to get and restore the previous mode.
        view_layer.objects.active = None

        for object in objects:
            # Deselect everything to use 'selection only' mode of the exporter.
            deselect_all(view_layer)

            # Select the exported object hierarchy.
            select_exportable(object)

            # Build the exported filename. 
            # Note: The file's extension is added by the export op.
            name = bpy.path.clean_name(object.name)
            filepath = os.path.join(export_directory, name)

            # Get a parameter-dictionary from the preferences.
            options = globals()[export_format + '_export_preferences'] | \
                to_dict(getattr(scene, export_format + '_batch_export_preferences'))
            
            # Set the sourceFilename so that external tools (Unity add-ons, etc.) can use it to 
            # open the original Blender file.
            scene.sourceFilename = bpy.data.filepath

            # Reset the root object's transform if desired.
            if preferences.reset_root_transform:
                location = object.location.copy()
                rotation = object.rotation_euler.copy()
                scale = object.scale.copy()

                object.location = Vector((0,0,0))
                object.rotation_euler = Vector((0,0,0))
                object.scale = Vector((1,1,1))

            try:
                # Export the object.
                export_op(filepath=filepath, **options)
                exported_objects.append(object)
            finally:
                # Restore the root object's transform.
                if preferences.reset_root_transform:
                    object.location = location
                    object.rotation_euler = rotation
                    object.scale = scale

    except Exception:
        report_exported_objects(report, exported_objects, export_directory)
        report({'WARNING'}, f"Failed exporting '{object.name}' to '{filepath}'")
        raise

    finally:
        # Restore the previous selection and active object.
        deselect_all(view_layer)
        for object in selection: object.select_set(True)
        view_layer.objects.active = active_object

    report_exported_objects( report, exported_objects, export_directory )
    return True

# Reports which objects were successfully exported.
def report_exported_objects( report, exported_objects, export_directory ):
    report({'INFO'}, "Exported [" + ", ".join([object.name for object in exported_objects]) +
        "] to " + get_truncated_directory(export_directory))

#
# Common Preferences
#
class BatchExportPreferences(PropertyGroup):
    # Get and set directory with relative path conversion if desired.
    def _get_directory(self): return self.get("_directory", "//")
    def _set_directory(self, value):
        if _use_relative_paths:
            try: self["_directory"] = bpy.path.relpath(value); return
            except Exception: ...
        self["_directory"] = value

    directory: StringProperty(name="Export Directory", default="//", subtype="DIR_PATH",
        get=_get_directory, set=_set_directory,
        description="The directory that models will be exported to")
    
    format_type: EnumProperty(items=BatchExportFormatType, 
        name="Export Format", default="gltf", description="The format files will be exported to")
    
    reset_root_transform: BoolProperty(name="Reset Root Transform", default=True,
        description="Resets the location, rotation, and scale of root objects")

#
# glTF
#

# Default export preferences (merged with ones set on the Scene) that are passed to the 
# built-in exporter.
# See: ...\Blender Foundation\Blender X.Y\X.Y\scripts\addons\io_scene_gltf2
gltf_export_preferences = dict(
    check_existing=False,
    use_selection=True,
    use_visible=False, # Export visible and hidden objects. See Object/Batch Export to skip.
    export_extras=True, # For custom exported properties.
    export_lights=True,
    export_cameras=True,
    export_skins=True,
    export_morph=True,
)

# Export Format Type - These must match built-in glTF exporter values.
GltfBatchExportFormatType = [
    ("GLB", "glTF Binary (.glb)", \
        "Exports a single file, with all data packed in binary form."),
    ("GLTF_SEPARATE", "glTF Separate (.glTF + .bin + textures)", \
        "Exports multiple files, with separate JSON, binary and texture data."),
    ("GLTF_EMBEDDED", "glTF Embedded (.glTF)", \
        "Exports a single file, with all data packed in JSON."),
]

# Exported Image Format Type - These must match built-in glTF exporter values.
GltfBatchExportImageFormatType = [
    ("AUTO", "Automatic", "Save PNGs as PNGs and JPEGs as JPEGs."),
    ("JPEG", "JPEG (.jpg)", "Save images as JPEGs. (Images that need alpha are saved as PNGs though.)"),
    ("NONE", "None", "Images will not be exported."),
]

# glTF export preferences.
# Important: These property annotation names *must* match the built-in glTF export op 
# parameter names!
class GltfBatchExportPreferences(PropertyGroup):
    export_format: EnumProperty(items=GltfBatchExportFormatType, name="glTF Format",
        default="GLB", description="The format files with be exported to")
    export_image_format: EnumProperty(items=GltfBatchExportImageFormatType, name="Image Format",
        default="NONE", description="The format image files with be exported to")
    export_yup: BoolProperty(name="+Y Up", default=True,
        description="Export using glTF convention, +Y up")
    export_texcoords: BoolProperty(name="UVs", default=True,
        description="Export texture coordinates per vertex")
    export_normals: BoolProperty(name="Normals", default=True,
        description="Export normals per vertex")
    export_tangents: BoolProperty(name="Tangents", default=False,
        description="Export tangents per vertex")
    export_colors: BoolProperty(name="Vertex Colors", default=False,
        description="Export colors per vertex")
    export_apply: BoolProperty(name="Apply Modifiers", default=True,
        description="Applies modifiers before exporting. (Prevents shape key export if True)")

#
# FBX
#

# Default export preferences (merged with ones set on the Scene) that are passed to the 
# built-in exporter.
# See: ...\Blender Foundation\Blender X.Y\X.Y\scripts\addons\io_scene_fbx
fbx_export_preferences = dict(
    check_existing=False,
    use_selection=True,
)

# FBX export preferences.
# Important: These property annotation names *must* match the built-in FBX export op 
# parameter names!
class FbxBatchExportPreferences(PropertyGroup):
    use_mesh_modifiers: BoolProperty(name="Apply Modifiers", default=True,
        description="Applies modifiers before exporting. (Prevents shape key export if True)")


#
# Operators
#

# Sets the batch_export setting on the selected objects.
# This should not be required if/when Blender supports multi-select property editing.
class SetBatchExported(Operator):
    """Sets selected objects to batch export or be skipped."""

    bl_idname = "object.set_batch_exported"
    bl_label = "Set Batch Exported"
    bl_options = {'REGISTER', 'UNDO'}

    export: BoolProperty(name="Export", default=True,
        description="If enabled, the object is exported")

    @classmethod
    def poll(cls, context): return len(context.selected_objects) > 0

    def execute(self, context):
        for object in context.selected_objects:
            object.batch_export = self.export
        return {'FINISHED'}


# Exports *all* objects in the current view-layer.
class BatchExportAll(Operator):
    """Export all root-level objects in the current view-layer to individual files."""

    bl_idname = "export_scene.batch_export_all"
    bl_label = "Batch Export All"

    def execute(self, context):
        # Determine which objects to export:
        #   * Objects with no parents (root nodes) that have batch exporting enabled.
        objects = [object for object in context.view_layer.objects.values()
            if object.parent is None and is_batch_exported(object)]

        export(context, context.scene.batch_export_preferences, objects, self.report)
        return {'FINISHED'}


# Exports selected objects in the current view-layer.
class BatchExportSelected(Operator):
    """Export selected root-level objects in the current view-layer to individual files."""

    bl_idname = "export_scene.batch_export_selected"
    bl_label = "Batch Export Selected"

    @classmethod
    def poll(cls, context):
       return len(context.selected_objects) > 0 and  is_export_directory_valid(context)

    def execute(self, context):
        # Determine which objects to export:
        #   * Objects with no parents (root nodes) that do not have the custom property
        #     'Object.batch_export' set to False.
        objects = [object for object in context.selected_objects]

        export(context, context.scene.batch_export_preferences, objects, self.report)
        return {'FINISHED'}

#
# Panels
#

# Scene 'Batch Exporter' panel.
class BatchExporterPanel(Panel):
    bl_label = "Batch Exporter"
    bl_idname = "SCENE_PT_batch_exporter"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        preferences = scene.batch_export_preferences
        layout.prop(preferences, 'directory')
        layout.prop(preferences, 'format_type')

        # UI for each property in the format-specific preferences.
        format_preferences = getattr(scene,
            preferences.format_type + '_batch_export_preferences')
        for property in format_preferences.__annotations__:
            layout.prop(format_preferences, property)

        # Additional common preferences.
        layout.prop(preferences, 'reset_root_transform')

        # 'Set Batch Exported' Operators
        row = layout.row()
        row.column().operator(SetBatchExported.bl_idname, text="Set Exported").export = True
        row.column().operator(SetBatchExported.bl_idname, text="Set Not-Exported").export = False

        # Export Operators
        row = layout.box().row()
        row.column().operator(BatchExportAll.bl_idname, text="Export All")
        row.column().operator(BatchExportSelected.bl_idname, text="Export Selected")


# Object 'Batch Export' panel.
class BatchExportObjectPanel(Panel):
    bl_label = "Batch Export"
    bl_idname = "OBJECT_PT_batch_export"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.prop(context.object, 'batch_export', text="")

    def draw(self, context): ...
        #layout = self.layout
        #layout.use_property_split = True
        #layout.use_property_decorate = False

#
# Registration
#

_classes = (SetBatchExported,
            BatchExportAll, BatchExportSelected, 
            BatchExporterPanel, BatchExportObjectPanel,
            BatchExportPreferences,
            GltfBatchExportPreferences, 
            FbxBatchExportPreferences,
)
_register, _unregister = bpy.utils.register_classes_factory(_classes)
_keymaps = []

# Called when the plugin is activated to register the classes and add the additional
# properties to objects, actions, etc.
def register():
    _register()

    # Store exporter properties on Scenes.
    bpy.types.Scene.batch_export_preferences = PointerProperty(type=BatchExportPreferences)
    # Note: preferences must be in the form: {BatchExportFormatType}_batch_export_preferences
    bpy.types.Scene.gltf_batch_export_preferences = PointerProperty(type=GltfBatchExportPreferences)
    bpy.types.Scene.fbx_batch_export_preferences = PointerProperty(type=FbxBatchExportPreferences)
    # Add 'sourceFilename' property to objects that can be used in Unity, etc. to open
    # the original Blender file.
    bpy.types.Scene.sourceFilename = StringProperty(name="Blender Filename")

    # Add 'batch_export' property to objects.    
    bpy.types.Object.batch_export = BoolProperty(name="Batch Export", default=True, \
            description="If unset, the object and its children will not be exported " +
                "during batch exports")

    # Add shortcuts: Ctrl+Alt+E (Export All), Ctrl+Alt+Shift+E (Export Selected)
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='Window', space_type='EMPTY', region_type='WINDOW')
    kmi = km.keymap_items.new(BatchExportAll.bl_idname, 'E', 'PRESS', ctrl=True, alt=True)
    _keymaps.append( (km, kmi) )
    kmi = km.keymap_items.new(BatchExportSelected.bl_idname, 'E', 'PRESS', ctrl=True, alt=True, shift=True)
    _keymaps.append( (km, kmi) )

def unregister():
    _unregister()

    # Remove shortcuts.
    for km, kmi in _keymaps: km.keymap_items.remove(kmi)
    _keymaps.clear()
