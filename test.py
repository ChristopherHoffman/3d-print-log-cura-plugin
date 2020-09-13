# Copyright (c) 2018 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.

import json
import os
import platform
import time
from typing import cast, Optional, Set, TYPE_CHECKING

from PyQt5.QtCore import pyqtSlot, QObject
from PyQt5.QtNetwork import QNetworkRequest

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


# This Extension runs in the background and sends several bits of information to the Ultimaker servers.
#       The data is only sent when the user in question gave permission to do so. All data is anonymous and
#       no model files are being sent (Just a SHA256 hash of the model).
class TestSliceInfo(QObject, Extension):
    # info_url = "https://stats.ultimaker.com/api/cura"
    plugin_version = "1.0.0"

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        Extension.__init__(self)

        from cura.CuraApplication import CuraApplication
        self._application = CuraApplication.getInstance()

        self._application.getOutputDeviceManager().writeStarted.connect(self._onWriteStarted)
        self._application.getPreferences().addPreference(
            "3dprintlog_info/send_slice_info", True)
        self._application.getPreferences().addPreference(
            "3dprintlog_info/asked_send_slice_info", False)

        self._more_info_dialog = None
        self._send_dialog = None
        self._example_data_content = None

        self._application.initializationFinished.connect(
            self._onAppInitialized)

    def _onAppInitialized(self):
        # DO NOT read any preferences values in the constructor because at the time plugins are created, no version
        # upgrade has been performed yet because version upgrades are plugins too!
        if self._more_info_dialog is None:
            self._more_info_dialog = self._createDialog("MoreInfoWindow.qml")

        # if self._send_dialog is None:
        #     self._send_dialog = self._createDialog("ModelChecker.qml")

    # Perform action based on user input.
    #   Note that clicking "Disable" won't actually disable the data sending, but rather take the user to preferences where they can disable it.
    def messageActionTriggered(self, message_id, action_id):
        self._application.getPreferences().setValue(
            "3dprintlog_info/asked_send_slice_info", True)
        if action_id == "MoreInfo":
            self.showMoreInfoDialog()
        self.send_slice_info_message.hide()

    def showMoreInfoDialog(self):
        if self._more_info_dialog is None:
            self._more_info_dialog = self._createDialog("MoreInfoWindow.qml")
        self._more_info_dialog.show()

    # def showSendDialog(self):
    #     if self._send_dialog is None:
    #         self._send_dialog = self._createDialog("ModelChecker.qml")
    #     self._send_dialog.show()

    def _createDialog(self, qml_name):
        Logger.log("d", "Creating dialog [%s]", qml_name)
        file_path = os.path.join(PluginRegistry.getInstance(
        ).getPluginPath(self.getPluginId()), qml_name)
        dialog = self._application.createQmlComponent(
            file_path, {"manager": self})
        return dialog

    @pyqtSlot(result=str)
    def getExampleData(self) -> Optional[str]:
        if self._example_data_content is None:
            plugin_path = PluginRegistry.getInstance().getPluginPath(self.getPluginId())
            if not plugin_path:
                Logger.log("e", "Could not get plugin path!",
                           self.getPluginId())
                return None
            file_path = os.path.join(plugin_path, "example_data.html")
            if file_path:
                with open(file_path, "r", encoding="utf-8") as f:
                    self._example_data_content = f.read()
        return self._example_data_content

    @pyqtSlot(bool)
    def setSendSliceInfo(self, enabled: bool):
        self._application.getPreferences().setValue(
            "3dprintlog_info/send_slice_info", enabled)

    def _getUserModifiedSettingKeys(self) -> list:
        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        user_modified_setting_keys = set()  # type: Set[str]

        for stack in [global_stack] + list(global_stack.extruders.values()):
            # Get all settings in user_changes and quality_changes
            all_keys = stack.userChanges.getAllKeys() | stack.qualityChanges.getAllKeys()
            user_modified_setting_keys |= all_keys

        return list(sorted(user_modified_setting_keys))

    def _onWriteStarted(self, output_device):
        try:
            if not self._application.getPreferences().getValue("3dprintlog_info/send_slice_info"):
                Logger.log(
                    "d", "'3dprintlog_info/send_slice_info' is turned off.")
                return  # Do nothing, user does not want to send data

            # self.showSendDialog()
            data = self.getCuraMetadata()
            data.update(self.getPrintTime())
            data.update(self.getPrintSettings())
            data["print_name"] = self.getPrintName()

            # Convert data to bytes
            test_output = json.dumps(data)
            binary_data = json.dumps(data).encode("utf-8")

            with open('C:\Temp\cura_output.json', 'w') as file:
                file.write(test_output)

            # Print Informationn
            # print_info_json = json.dumps(print_information)
            # with open('C:\Temp\cura_print_info.json', 'w') as file:
            #     file.write(print_info_json)

            # Global Stack Informationn
            # global_stack_json = json.dumps(global_stack)
            # with open('C:\Temp\cura_global_stack.json', 'w') as file:
            #     file.write(global_stack_json)

            import webbrowser
            try:
                # python2
                from urllib import urlencode
            except ImportError:
                # python3
                from urllib.parse import urlencode
            query_params = urlencode(data)
            url = "https://localhost:4200/prints/new/edit?" + query_params
            webbrowser.open(url, new=0, autoraise=True)

            # Send slice info non-blocking
            # network_manager = self._application.getHttpRequestManager()
            # network_manager.post(self.info_url, data = binary_data,
            #                      callback = self._onRequestFinished, error_callback = self._onRequestError)

        except Exception:
            # We really can't afford to have a mistake here, as this would break the sending of g-code to a device
            # (Either saving or directly to a printer). The functionality of the slice data is not *that* important.
            # But we should be notified about these problems of course.
            Logger.logException(
                "e", "Exception raised while sending slice info.")

    def _onRequestFinished(self, reply: "QNetworkReply") -> None:
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status_code == 200:
            Logger.log("i", "SliceInfo sent successfully")
            return

        data = reply.readAll().data().decode("utf-8")
        Logger.log(
            "e", "SliceInfo request failed, status code %s, data: %s", status_code, data)

    def _onRequestError(self, reply: "QNetworkReply", error: "QNetworkReply.NetworkError") -> None:
        Logger.log("e", "Got error for SliceInfo request: %s",
                   reply.errorString())

    def getCuraMetadata(self):
        data = dict()
        data["time_stamp"] = time.time()
        data["cura_version"] = self._application.getVersion()
        data["cura_build_type"] = ApplicationMetadata.CuraBuildType
        data["plugin_version"] = self.plugin_version

        return data

    def getPrintTime(self):
        data = dict()
        print_information = self._application.getPrintInformation()
        data["estimated_print_time"] = int(
            print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))

        return data

    def getPrintSettings(self):
        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

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

        return print_settings

    def getPrintName(self):
        for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
            if node.callDecoration("isSliceable"):
                return node.getName()

        return ''

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

        # Send the name of the output device type that is used.
        # data["output_to"] = type(output_device).__name__

        return data
