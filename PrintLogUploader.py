import json
import os
import platform
import time
from typing import cast, Optional, Set, TYPE_CHECKING

from PyQt5.QtCore import pyqtSlot, QObject
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPixmap

from UM.Extension import Extension
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.PluginRegistry import PluginRegistry
from UM.Qt.Duration import DurationFormat

from cura import ApplicationMetadata

if TYPE_CHECKING:
    from PyQt5.QtNetwork import QNetworkReply


catalog = i18nCatalog("cura")


class PrintLogUploader(QObject, Extension):
    '''This extension lets a user to create a new print on https://www.3dprintlog.com when saving a print in Cura.
    3D Print Logs's new print form is pre-populated by Cura's print settings and estimated print time/filament.
    Requires the user to have an account and be logged into 3D Print Log before they can save any information.
    '''

    plugin_version = "1.0.0"
    #new_print_url = "https://localhost:4200/prints/new/cura"
    new_print_url = "https://www.3dprintlog.com/prints/new/cura"

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        Extension.__init__(self)

        from cura.CuraApplication import CuraApplication
        self._application = CuraApplication.getInstance()

        self._application.getOutputDeviceManager().writeStarted.connect(self._onWriteStarted)

        self.addMenuItem("Send to 3D Print Log", self._sendTo3DPrintLog)

    def _onWriteStarted(self, output_device):
        '''Send to 3D Print Log when gcode is saved.'''
        try:
            send_to_3D_print_log = self._shouldSendTo3DPrintLog()
            if not send_to_3D_print_log:
                Logger.log(
                    "d", "User denied the prompt")
                return  # Do nothing, user does not want to send data

            self._sendTo3DPrintLog()

        except Exception:
            # We really can't afford to have a mistake here, as this would break the sending of g-code to a device
            # (Either saving or directly to a printer). The functionality of the slice data is not *that* important.
            # But we should be notified about these problems of course.
            Logger.logException(
                "e", "Exception raised in _onWriteStarted")

    def _sendTo3DPrintLog(self):
        '''Gets the print settings and send them to 3D Print Log'''
        try:
            data = self._getPrintSettings()
            self._openBrowser(data)

            # For debugging purposes:
            # test_output = json.dumps(data)

            # with open('C:\Temp\cura_output.json', 'w') as file:
            #     file.write(test_output)
        except Exception:
            Logger.logException(
                "e", "Exception raised while sending print info in _sendTo3DPrintLog.")

    def _shouldSendTo3DPrintLog(self) -> bool:
        '''Returns true if this print should be sent.'''
        dialog = self._createConfirmationDialog()

        returnValue = dialog.exec()

        return returnValue == QMessageBox.Ok

    def _createConfirmationDialog(self):
        '''Create a message box prompting the user if they want to send this print information.'''
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText("Would you like to send to 3Dprintlog.com?")
        msgBox.setWindowTitle("Send to 3D Print Log?")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msgBox.setDefaultButton(QMessageBox.Ok)

        self._add3DPrintLogLogo(msgBox)

        return msgBox

    def _add3DPrintLogLogo(self, msgBox):
        '''Adds the 3D Print Log Logo as a message boxes icon.'''
        p = QPixmap()
        plugin_path = PluginRegistry.getInstance().getPluginPath(self.getPluginId())
        if not plugin_path:
            Logger.log("e", "Could not get plugin path!",
                       self.getPluginId())
            return None
        file_path = os.path.join(plugin_path, "3DPrintLog_logo_64px.jpg")
        p.load(file_path)
        msgBox.setIconPixmap(p)

    def _getPrintSettings(self):
        '''Returns a dictionary with all of the print settings.'''
        data = dict()
        data.update(self.getCuraMetadata())
        data.update(self.getPrintTime())
        data.update(self.getPrintSettings())
        data.update(self.getMaterialUsage())
        data["print_name"] = self.getPrintName()

        return data

    def _openBrowser(self, data):
        '''Opens 3D Print Log website and passes the data as query params.'''
        import webbrowser
        try:
            # python2
            from urllib import urlencode
        except ImportError:
            # python3
            from urllib.parse import urlencode
        query_params = urlencode(data)
        url = self.new_print_url + "?" + query_params
        webbrowser.open(url, new=0, autoraise=True)

    def getCuraMetadata(self):
        '''Returns meta data about cura and the plugin itself.'''
        data = dict()
        data["time_stamp"] = time.time()
        data["cura_version"] = self._application.getVersion()
        data["cura_build_type"] = ApplicationMetadata.CuraBuildType
        data["plugin_version"] = self.plugin_version

        return data

    def getPrintTime(self):
        '''Returns the estimated print time in seconds.'''
        data = dict()
        print_information = self._application.getPrintInformation()
        data["estimated_print_time_seconds"] = int(
            print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))

        return data

    def getPrintSettings(self):
        '''Returns a dictionary of print settings.'''
        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        print_settings = dict()

        # Quality
        print_settings["layer_height"] = global_stack.getProperty(
            "layer_height", "value")
        print_settings["top_thickness"] = global_stack.getProperty(
            "top_thickness", "value")
        print_settings["bottom_thickness"] = global_stack.getProperty(
            "bottom_thickness", "value")

        # Shell
        print_settings["wall_line_count"] = global_stack.getProperty(
            "wall_line_count", "value")

        # Infill
        print_settings["infill_sparse_density"] = global_stack.getProperty(
            "infill_sparse_density", "value")
        print_settings["infill_pattern"] = global_stack.getProperty(
            "infill_pattern", "value")
        print_settings["gradual_infill_steps"] = global_stack.getProperty(
            "gradual_infill_steps", "value")

        # Material

        # Speed

        # Travel
        print_settings["retraction_enable"] = global_stack.getProperty(
            "retraction_enable", "value")

        # Cooling

        # Support
        print_settings["support_enabled"] = global_stack.getProperty(
            "support_enable", "value")
        print_settings["support_type"] = global_stack.getProperty(
            "support_type", "value")
        print_settings["support_extruder_nr"] = int(
            global_stack.getExtruderPositionValueWithDefault("support_extruder_nr"))

        # Build Plate Adhesion
        print_settings["adhesion_type"] = global_stack.getProperty(
            "adhesion_type", "value")

        # Dual Extrusion
        print_settings["prime_tower_enable"] = global_stack.getProperty(
            "prime_tower_enable", "value")

        # Mesh Fixes

        # Special modes
        print_settings["print_sequence"] = global_stack.getProperty(
            "print_sequence", "value")
        print_settings["mold_enabled"] = global_stack.getProperty(
            "mold_enabled", "value")
        print_settings["magic_spiralize"] = global_stack.getProperty(
            "magic_spiralize", "value")
        print_settings["ooze_shield_enabled"] = global_stack.getProperty(
            "ooze_shield_enabled", "value")

        # Experimental
        print_settings["wireframe_enabled"] = global_stack.getProperty(
            "wireframe_enabled", "value")
        print_settings["magic_fuzzy_skin_enabled"] = global_stack.getProperty(
            "magic_fuzzy_skin_enabled", "value")
        print_settings["draft_shield_enabled"] = global_stack.getProperty(
            "draft_shield_enabled", "value")
        print_settings["adaptive_layer_height_enabled"] = global_stack.getProperty(
            "adaptive_layer_height_enabled", "value")
        print_settings["ironing_enabled"] = global_stack.getProperty(
            "ironing_enabled", "value")

        print_settings["machine_name"] = global_stack.getProperty(
            "machine_name", "value")

        return print_settings

    def getPrintName(self):
        '''Returns the name of the Print Object.'''
        for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
            if node.callDecoration("isSliceable"):
                return node.getName()

        return ''

    def getMaterialUsage(self):
        '''Returns a dictionary containing the material used in milligrams.'''
        print_information = self._application.getPrintInformation()

        data = dict()
        material_used_g = sum(print_information.materialWeights)
        material_used_mg = round(material_used_g * 1000)
        data["material_used_mg"] = material_used_mg

        return data

    def _getUserModifiedSettingKeys(self) -> list:
        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        user_modified_setting_keys = set()  # type: Set[str]

        for stack in [global_stack] + list(global_stack.extruders.values()):
            # Get all settings in user_changes and quality_changes
            all_keys = stack.userChanges.getAllKeys() | stack.qualityChanges.getAllKeys()
            user_modified_setting_keys |= all_keys

        return list(sorted(user_modified_setting_keys))

    def getFullInfo(self):
        machine_manager = self._application.getMachineManager()
        print_information = self._application.getPrintInformation()

        global_stack = machine_manager.activeMachine

        data = dict()  # The data that we're going to submit.
        data["time_stamp"] = time.time()
        data["schema_version"] = 0
        data["cura_version"] = self._application.getVersion()
        data["cura_build_type"] = ApplicationMetadata.CuraBuildType

        active_mode = self._application.getPreferences().getValue("cura/active_mode")
        if active_mode == 0:
            data["active_mode"] = "recommended"
        else:
            data["active_mode"] = "custom"

        data["camera_view"] = self._application.getPreferences(
        ).getValue("general/camera_perspective_mode")
        if data["camera_view"] == "orthographic":
            # The database still only recognises the old name "orthogonal".
            data["camera_view"] = "orthogonal"

        definition_changes = global_stack.definitionChanges
        machine_settings_changed_by_user = False
        if definition_changes.getId() != "empty":
            # Now a definition_changes container will always be created for a stack,
            # so we also need to check if there is any instance in the definition_changes container
            if definition_changes.getAllKeys():
                machine_settings_changed_by_user = True

        data["machine_settings_changed_by_user"] = machine_settings_changed_by_user
        data["language"] = self._application.getPreferences(
        ).getValue("general/language")
        data["os"] = {"type": platform.system(
        ), "version": platform.version()}

        data["active_machine"] = {"definition_id": global_stack.definition.getId(),
                                  "manufacturer": global_stack.definition.getMetaDataEntry("manufacturer", "")}

        # add extruder specific data to slice info
        data["extruders"] = []
        extruders = list(global_stack.extruders.values())
        extruders = sorted(
            extruders, key=lambda extruder: extruder.getMetaDataEntry("position"))

        for extruder in extruders:
            extruder_dict = dict()
            extruder_dict["active"] = machine_manager.activeStack == extruder
            Logger.log("i", "")
            extruder_dict["material"] = {"GUID": extruder.material.getMetaData().get("GUID", ""),
                                         "type": extruder.material.getMetaData().get("material", ""),
                                         "brand": extruder.material.getMetaData().get("brand", "")
                                         }
            extruder_position = int(
                extruder.getMetaDataEntry("position", "0"))
            if len(print_information.materialLengths) > extruder_position:
                extruder_dict["material_used"] = print_information.materialLengths[extruder_position]
            extruder_dict["variant"] = extruder.variant.getName()
            extruder_dict["nozzle_size"] = extruder.getProperty(
                "machine_nozzle_size", "value")

            extruder_settings = dict()
            extruder_settings["wall_line_count"] = extruder.getProperty(
                "wall_line_count", "value")
            extruder_settings["retraction_enable"] = extruder.getProperty(
                "retraction_enable", "value")
            extruder_settings["infill_sparse_density"] = extruder.getProperty(
                "infill_sparse_density", "value")
            extruder_settings["infill_pattern"] = extruder.getProperty(
                "infill_pattern", "value")
            extruder_settings["gradual_infill_steps"] = extruder.getProperty(
                "gradual_infill_steps", "value")
            extruder_settings["default_material_print_temperature"] = extruder.getProperty(
                "default_material_print_temperature", "value")
            extruder_settings["material_print_temperature"] = extruder.getProperty(
                "material_print_temperature", "value")
            extruder_dict["extruder_settings"] = extruder_settings
            data["extruders"].append(extruder_dict)

        data["intent_category"] = global_stack.getIntentCategory()
        data["quality_profile"] = global_stack.quality.getMetaData().get(
            "quality_type")

        data["user_modified_setting_keys"] = self._getUserModifiedSettingKeys()

        data["models"] = []
        # Listing all files placed on the build plate
        for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
            if node.callDecoration("isSliceable"):
                model = dict()
                model["hash"] = node.getMeshData().getHash()
                bounding_box = node.getBoundingBox()
                if not bounding_box:
                    continue
                model["bounding_box"] = {"minimum": {"x": bounding_box.minimum.x,
                                                     "y": bounding_box.minimum.y,
                                                     "z": bounding_box.minimum.z},
                                         "maximum": {"x": bounding_box.maximum.x,
                                                     "y": bounding_box.maximum.y,
                                                     "z": bounding_box.maximum.z}}
                model["transformation"] = {"data": str(
                    node.getWorldTransformation().getData()).replace("\n", "")}
                extruder_position = node.callDecoration(
                    "getActiveExtruderPosition")
                model["extruder"] = 0 if extruder_position is None else int(
                    extruder_position)

                model_settings = dict()
                model_stack = node.callDecoration("getStack")
                if model_stack:
                    model_settings["support_enabled"] = model_stack.getProperty(
                        "support_enable", "value")
                    model_settings["support_extruder_nr"] = int(
                        model_stack.getExtruderPositionValueWithDefault("support_extruder_nr"))

                    # Mesh modifiers;
                    model_settings["infill_mesh"] = model_stack.getProperty(
                        "infill_mesh", "value")
                    model_settings["cutting_mesh"] = model_stack.getProperty(
                        "cutting_mesh", "value")
                    model_settings["support_mesh"] = model_stack.getProperty(
                        "support_mesh", "value")
                    model_settings["anti_overhang_mesh"] = model_stack.getProperty(
                        "anti_overhang_mesh", "value")

                    model_settings["wall_line_count"] = model_stack.getProperty(
                        "wall_line_count", "value")
                    model_settings["retraction_enable"] = model_stack.getProperty(
                        "retraction_enable", "value")

                    # Infill settings
                    model_settings["infill_sparse_density"] = model_stack.getProperty(
                        "infill_sparse_density", "value")
                    model_settings["infill_pattern"] = model_stack.getProperty(
                        "infill_pattern", "value")
                    model_settings["gradual_infill_steps"] = model_stack.getProperty(
                        "gradual_infill_steps", "value")

                model["model_settings"] = model_settings

                data["models"].append(model)

        print_times = print_information.printTimes()
        data["print_times"] = {"travel": int(print_times["travel"].getDisplayString(DurationFormat.Format.Seconds)),
                               "support": int(print_times["support"].getDisplayString(DurationFormat.Format.Seconds)),
                               "infill": int(print_times["infill"].getDisplayString(DurationFormat.Format.Seconds)),
                               "total": int(print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))}

        print_settings = dict()
        print_settings["layer_height"] = global_stack.getProperty(
            "layer_height", "value")

        # Support settings
        print_settings["support_enabled"] = global_stack.getProperty(
            "support_enable", "value")
        print_settings["support_extruder_nr"] = int(
            global_stack.getExtruderPositionValueWithDefault("support_extruder_nr"))

        # Platform adhesion settings
        print_settings["adhesion_type"] = global_stack.getProperty(
            "adhesion_type", "value")

        # Shell settings
        print_settings["wall_line_count"] = global_stack.getProperty(
            "wall_line_count", "value")
        print_settings["retraction_enable"] = global_stack.getProperty(
            "retraction_enable", "value")

        # Prime tower settings
        print_settings["prime_tower_enable"] = global_stack.getProperty(
            "prime_tower_enable", "value")

        # Infill settings
        print_settings["infill_sparse_density"] = global_stack.getProperty(
            "infill_sparse_density", "value")
        print_settings["infill_pattern"] = global_stack.getProperty(
            "infill_pattern", "value")
        print_settings["gradual_infill_steps"] = global_stack.getProperty(
            "gradual_infill_steps", "value")

        print_settings["print_sequence"] = global_stack.getProperty(
            "print_sequence", "value")

        data["print_settings"] = print_settings

        return data
