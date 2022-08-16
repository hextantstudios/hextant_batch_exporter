# Blender Add-on: Batch Exporter

It is often easier to work with multiple objects in a single Blender file, for example when different models share the same texture. This add-on makes it possible to export multiple root objects (and their children) from a single Blender file to individual files on disk. glTF and FBX are currently supported, though adding support for other file types is quite easy.

## Installation

* Download the latest release from [here](https://github.com/hextantstudios/hextant_python_debugger/releases/latest/download/hextant_batch_exporter.zip) or clone it using Git to your custom Blender `...\scripts\addons\` folder.
* From Blender's Main Menu:
  * *Edit / Preferences*
  * Click the *Install* button and select the downloaded zip file.
  * Check the check-box next to the add-on to activate it.

## Batch Exporter Configuration

The add-on can be found in the *Scene Properties* tab in Blender.

* *Export Directory* - The location to export model file to. Note that the add-on tries to use relative paths from the Blender file if possible. (This can be disable at the top of the add-on's script file.)
* *Export Format* - The file format used to export. The built-in exporter must be installed for the selected file type.
* *File Format Settings* - After selecting an export format, format-specific settings are displayed. Currently this list includes some of the more common settings. If a new setting needs to be added, it is quite easy to expose one in the add-on's script.
* *Set Exported / Set Not-Exported* - This sets a per-object property to mark an object for export. This can also be changed on a selected object from the *Object Properties* tab in Blender.
* *Export All / Selected* - Click to export all configured root objects or just the selected ones. (`Ctrl+Alt E` / `Ctrl+Alt+Shift E`)