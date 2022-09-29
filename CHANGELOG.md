# Changelog

## 2.0.5

- Adds a new "Include Object Details in Notes" setting, which is enabled by default. This will add the stl name, position, and size information directly within the Notes section went sent to 3D Print Log.
- Sends the currently selected machine ID for a future 3D Print Log feature which will automatically select the correct printer.

## 2.0.4

- Added a dialog which displays the New Print Url when the plugin was unable to automatically detect and open the webbrowser.

## 2.0.3

- Fix the Settings dialog to properly display the Setting Category.
- Settings Dialog will now display with the correct Cura Theme.

## 2.0.2

- Adds new option to bypass the "Would you like to send to 3D Print Log" prompt, with an option to 'Always Ask', to 'Always Send after save', or 'Never Send after save'.
- Removes the old Bypass Prompt checkbox, since the new dropdown replaces it.

## 2.0.1

- Adds new setting which skips the "Do you want to send to 3D Print Log?" prompt and always send print information after saving.
- Adds backward compatibility support for Cura 4

## 2.0.0

### Breaking Changes:

This update is to support Cura 5, which updated from Qt5 to Qt6. This is a breaking change due to substantial UI changes.

- Added support to Cura 5, removed support for previous SDK versions.

## 1.2.1

- Added ability to send a snapshot of the build plate as the print image. (Enabled by default).

## 1.2.0

- Added Settings Dialog to allow for customizing of what settings are logged.
- Added option to record Profile Name and Filament Names
- Minimum supported version: Cura 4.5

## 1.1.0

- Added support for multiple extruders
- Added support for Cura 4.8
- Fixed bug where slicer settings would not correctly log settings the user changed without saving the profile.
- Plugin will only try and log files that have been sliced.

## 1.0.0

Initial Release
