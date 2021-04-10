import json
import os
import platform
import time
from typing import cast, Optional, Set, TYPE_CHECKING

from PyQt5.QtQml import qmlRegisterType
from PyQt5.QtCore import pyqtSlot, QObject, QUrl
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPixmap

from cura.CuraApplication import CuraApplication
from UM.Extension import Extension
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.PluginRegistry import PluginRegistry
from UM.Qt.Duration import DurationFormat

from cura import ApplicationMetadata

from . import PrintLogSettingsVisibilityHandler

if TYPE_CHECKING:
    from PyQt5.QtNetwork import QNetworkReply


catalog = i18nCatalog("cura")


class PrintLogUploader(QObject, Extension):
    '''This extension lets a user to create a new print on https://www.3dprintlog.com when saving a print in Cura.
    3D Print Logs's new print form is pre-populated by Cura's print settings and estimated print time/filament.
    Requires the user to have an account and be logged into 3D Print Log before they can save any information.
    '''

    plugin_version = "1.2.0"
    new_print_url = "https://localhost:4200/prints/new/cura"
    api_url = "https://localhost:5001/api/Cura/settings"
    # new_print_url = "https://www.3dprintlog.com/prints/new/cura"

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        Extension.__init__(self)

        self._application = CuraApplication.getInstance()

        self._application.getOutputDeviceManager().writeStarted.connect(self._onWriteStarted)

        self.addMenuItem("Send to 3D Print Log", self._onMenuButtonClicked)
        self.addMenuItem("Configure Settings to Log", self.showSettingsDialog)

        default_logged_settings = {
            "default_material_print_temperature",
            "default_material_bed_temperature",
            "material_standby_temperature",
            #"material_flow_temp_graph",
            "cool_fan_speed",
            "retraction_amount",
            "retraction_speed",
            "material_flow",
        }

        CuraApplication.getInstance().getPreferences().addPreference(
            "3d_print_log/logged_settings",
            ";".join(default_logged_settings)
        )

        CuraApplication.getInstance().engineCreatedSignal.connect(self._onEngineCreated)

    def _onMenuButtonClicked(self):
        '''Executed when the menu button is clicked.'''
        send_to_3D_print_log = self._hasSlicedModel()
        if not send_to_3D_print_log:
            Logger.log(
                "d", "No file sliced, not sending to 3D Print Log")
            self._createDialog(
                "Please slice file before sending to 3D Print Log.", "File Not Sliced").exec()
            return

        self._sendTo3DPrintLog()

    def _onEngineCreated(self):
        qmlRegisterType(
            PrintLogSettingsVisibilityHandler.PrintLogSettingsVisibilityHandler,
            "Cura", 1, 0, "PrintLogSettingsVisibilityHandler"
        )

    def showSettingsDialog(self):
        path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "qml", "SettingsDialog.qml")
        self._settings_dialog = CuraApplication.getInstance(
        ).createQmlComponent(path, {"manager": self})
        self._settings_dialog.show()

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
            data = dict()
            data["curaVersion"] = self._application.getVersion()
            data["pluginVersion"] = self.plugin_version
            data["settings"] = self._getPrintSettings()

            self._sendToApi(data)

            # For debugging purposes:
            # test_output = json.dumps(data)

            # with open('C:\Temp\cura_output.json', 'w') as file:
            #     file.write(test_output)

        except Exception:
            Logger.logException(
                "e", "Exception raised while sending print info in _sendTo3DPrintLog.")

    def _shouldSendTo3DPrintLog(self) -> bool:
        '''Returns true if this print should be sent.'''

        hasSliced = self._hasSlicedModel()
        if not hasSliced:
            return False

        dialog = self._createConfirmationDialog()

        returnValue = dialog.exec()

        return returnValue == QMessageBox.Ok

    def _hasSlicedModel(self) -> bool:
        '''Checks to see if the model has been sliced'''
        scene = self._application.getController().getScene()
        # If the scene does not have a gcode, do nothing
        if not hasattr(scene, "gcode_dict"):
            return False
        gcode_dict = getattr(scene, "gcode_dict")
        if not gcode_dict:
            return False

        return True

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

    def _createDialog(self, text, title):
        '''Create a messsage box with a title and text'''
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText(text)
        msgBox.setWindowTitle(title)
        msgBox.setStandardButtons(QMessageBox.Ok)
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
        data.update(self.getExtruderSettings())
        data["global"] = self.getAllGlobalSettings()
        data["extruders"] = self.getAllExtruderSettings()
        data["print_name"] = self.getPrintName()

        return data

    def _sendToApi(self, data):
        '''Opens 3D Print Log website and passes the data as query params.'''
        # Convert data to bytes
        binary_data = json.dumps(data).encode("utf-8")

        Logger.log("i", "data: %s",
                   binary_data)

        # Send slice info non-blocking
        network_manager = self._application.getHttpRequestManager()

        # request = QNetworkRequest(QUrl(self.api_url))
        # request.setHeader(QNetworkRequest.ContentTypeHeader,
        #                   "application/json")

        network_manager.post(self.api_url, data=binary_data,
                             callback=self._onRequestFinished, error_callback=self._onRequestError)

    def _onRequestFinished(self, reply: "QNetworkReply") -> None:
        Logger.log("i", "reply %s",
                   reply)
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status_code == 200:
            results = json.loads(reply.readAll().data().decode("utf-8"))
            newGuid = results["newSettingId"]
            Logger.log("i", "Settings Send Successfully",
                       reply.readAll().data().decode("utf-8"), newGuid)

            data = dict()
            data["cura_version"] = self._application.getVersion()
            data["plugin_version"] = self.plugin_version
            data["settingId"] = newGuid
            self._openBrowser(data)
            return

        data = reply.readAll().data().decode("utf-8")
        Logger.log(
            "e", "Settings Api request failed, status code %s, data: %s", status_code, data)

    def _onRequestError(self, reply: "QNetworkReply", error: "QNetworkReply.NetworkError") -> None:
        Logger.log("e", "Got error for Send Settings request: %s",
                   reply.errorString())

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

    def getAllGlobalSettings(self):
        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        data = dict()

        # Get all settings in user_changes and quality_changes
        all_keys = global_stack.getAllKeys()

        for key in all_keys:
            setting = dict()
            setting["label"] = global_stack.getProperty(
                key, "label")
            setting["description"] = global_stack.getProperty(
                key, "description")
            setting["value"] = global_stack.getProperty(key, "value")
            data[key] = setting

        return data

    def getAllExtruderSettings(self):
        '''Return the collection of extruder-specific settings as a flattened dictionary.'''
        data = dict()

        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        extruders = global_stack.extruderList
        extruders = sorted(
            extruders, key=lambda extruder: extruder.getMetaDataEntry("position"))

        for extruder in extruders:
            extruder_position = int(extruder.getMetaDataEntry("position", "0"))
            extruder_dict = dict()

            # Flatten each extruder setting array by prepending the extruder index as ex#_ to each setting
            extruderName = "ex" + str(extruder_position) + "_"

            print_information = self._application.getPrintInformation()
            if len(print_information.materialLengths) > extruder_position:
                extruder_dict[extruderName +
                              "material_used"] = print_information.materialLengths[extruder_position]

            all_keys = extruder.getAllKeys()

            for key in all_keys:
                # extruder_dict[extruderName +
                #               key] = extruder.getProperty(key, "value")

                setting = dict()
                setting["label"] = extruder.getProperty(
                    key, "label")
                setting["description"] = extruder.getProperty(
                    key, "description")
                setting["value"] = extruder.getProperty(key, "value")
                extruder_dict[extruderName +
                              key] = setting

            data.update(extruder_dict)

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

    def getExtruderSettings(self):
        '''Return the collection of extruder-specific settings as a flattened dictionary.'''
        data = dict()

        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        extruders = global_stack.extruderList
        extruders = sorted(
            extruders, key=lambda extruder: extruder.getMetaDataEntry("position"))

        for extruder in extruders:
            extruder_position = int(extruder.getMetaDataEntry("position", "0"))
            extruder_dict = dict()

            # Flatten each extruder setting array by prepending the extruder index as ex#_ to each setting
            extruderName = "ex" + str(extruder_position) + "_"

            print_information = self._application.getPrintInformation()
            if len(print_information.materialLengths) > extruder_position:
                extruder_dict[extruderName +
                              "material_used"] = print_information.materialLengths[extruder_position]

            extruder_dict[extruderName +
                          "variant"] = extruder.variant.getName()
            extruder_dict[extruderName + "nozzle_size"] = extruder.getProperty(
                "machine_nozzle_size", "value")

            extruder_dict[extruderName + "wall_line_count"] = extruder.getProperty(
                "wall_line_count", "value")
            extruder_dict[extruderName + "top_thickness"] = extruder.getProperty(
                "top_thickness", "value")
            extruder_dict[extruderName + "top_layers"] = extruder.getProperty(
                "top_layers", "value")
            extruder_dict[extruderName + "bottom_thickness"] = extruder.getProperty(
                "bottom_thickness", "value")
            extruder_dict[extruderName + "bottom_layers"] = extruder.getProperty(
                "bottom_layers", "value")
            extruder_dict[extruderName + "retraction_enable"] = extruder.getProperty(
                "retraction_enable", "value")
            extruder_dict[extruderName + "infill_sparse_density"] = extruder.getProperty(
                "infill_sparse_density", "value")
            extruder_dict[extruderName + "infill_pattern"] = extruder.getProperty(
                "infill_pattern", "value")
            extruder_dict[extruderName + "gradual_infill_steps"] = extruder.getProperty(
                "gradual_infill_steps", "value")
            extruder_dict[extruderName + "default_material_print_temperature"] = extruder.getProperty(
                "default_material_print_temperature", "value")
            extruder_dict[extruderName + "material_print_temperature"] = extruder.getProperty(
                "material_print_temperature", "value")

            data.update(extruder_dict)

        return data

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
