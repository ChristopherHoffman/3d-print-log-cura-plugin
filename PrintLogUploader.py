import json
import os
import platform
import time
import collections
from typing import cast, Optional, Set, TYPE_CHECKING

from PyQt5.QtQml import qmlRegisterType
from PyQt5.QtCore import pyqtSlot, QObject, QUrl, QBuffer
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPixmap, QImage

from cura.CuraApplication import CuraApplication
from cura.Machines.ContainerTree import ContainerTree
from cura.Snapshot import Snapshot
from UM.Extension import Extension
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.PluginRegistry import PluginRegistry
from UM.Qt.Duration import DurationFormat

from cura import ApplicationMetadata

from . import PrintLogSettingsVisibilityHandler
from . import PrintLogSettingDefinitionsModel

if TYPE_CHECKING:
    from PyQt5.QtNetwork import QNetworkReply


catalog = i18nCatalog("cura")


class PrintLogUploader(QObject, Extension):
    '''This extension lets a user to create a new print on https://www.3dprintlog.com when saving a print in Cura.
    3D Print Logs's new print form is pre-populated by Cura's print settings and estimated print time/filament.
    Requires the user to have an account and be logged into 3D Print Log before they can save any information.
    '''

    plugin_version = "1.2.0"
    # new_print_url = "https://localhost:4200/prints/new/cura"
    # api_url = "https://localhost:5001/api/Cura/settings"

    new_print_url = "https://www.3dprintlog.com/prints/new/cura"
    api_url = "https://api.3dprintlog.com/api/Cura/settings"

    default_logged_settings = {
        "layer_height",
        "line_width",
        "wall_line_count",
        "top_thickness",
        "bottom_thickness",
        "infill_sparse_density",
        "infill_pattern",
        "material_print_temperature",
        "material_bed_temperature",
        "speed_print",
        "cool_fan_enabled",
        "cool_fan_speed",
        "support_enable",
        "support_structure",
        "support_type",
        "adhesion_type",
    }

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        Extension.__init__(self)

        self._application = CuraApplication.getInstance()

        self._application.getOutputDeviceManager().writeStarted.connect(self._onWriteStarted)

        self.addMenuItem("Send to 3D Print Log", self._onSendMenuButtonClicked)
        self.addMenuItem("Configure Settings to Log", self.showSettingsDialog)

        self._application.getPreferences().addPreference(
            "3d_print_log/logged_settings",
            ";".join(self.default_logged_settings)
        )
        self._application.getPreferences().addPreference(
            "3d_print_log/include_profile_name",
            True
        )
        self._application.getPreferences().addPreference(
            "3d_print_log/include_filament_name",
            True
        )

        self._application.engineCreatedSignal.connect(self._onEngineCreated)

    def _onSendMenuButtonClicked(self):
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

            Logger.log("i", "Generating Test Log")
            snapshot = self.generateSnapshot()

            data = dict()
            data["curaVersion"] = self._application.getVersion()
            data["pluginVersion"] = self.plugin_version

            settings = dict()
            settings["note"] = self._generateNotes()
            settings["print_name"] = self._getPrintName()
            settings.update(self._getCuraMetadata())
            settings.update(self._getPrintTime())
            settings.update(self._getMaterialUsage())

            if snapshot:
                settings["snapshot"] = snapshot.data(
                ).toBase64().data().decode("utf-8")

            data["settings"] = settings

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

    def _sendToApi(self, data):
        '''Sends the data to the 3D Print Log api.'''
        # Convert setting data to bytes
        binary_data = json.dumps(data).encode("utf-8")

        # Sent
        network_manager = self._application.getHttpRequestManager()
        network_manager.post(self.api_url, data=binary_data,
                             callback=self._onRequestFinished, error_callback=self._onRequestError)

    def _onRequestFinished(self, reply: "QNetworkReply") -> None:
        '''Handle the response from the API after sending the settings.'''
        status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status_code == 200:
            # API will return a GUID that can be used to retrieve the setting information that was saved.
            results = json.loads(reply.readAll().data().decode("utf-8"))
            newGuid = results["newSettingId"]

            # Use that GUID and some cura metadata to open 3D Print Log website in a browser.
            # The website use the GUID to retrieve the setting information and populate the print.
            data = dict()
            data["cura_version"] = self._application.getVersion()
            data["plugin_version"] = self.plugin_version
            data["settingId"] = newGuid
            self._openBrowser(data)
            return

        # If the response was non-successful, then log the error.
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

    def generateSnapshot(self) -> Optional[QBuffer]:
        try:
            Logger.log("i", "Generating Snapshot")
            # Attempt to store the thumbnail, if any:
            # backend = CuraApplication.getInstance().getBackend()
            # snapshot = None if getattr(
            #     backend, "getLatestSnapshot", None) is None else backend.getLatestSnapshot()

            snapshot = None
            if not CuraApplication.getInstance().isVisible:
                Logger.log(
                    "i", "Can't create snapshot when renderer not initialized.")
                return None
            Logger.log("i", "Creating thumbnail image.")
            try:
                snapshot = Snapshot.snapshot(width=600, height=600)
            except:
                Logger.log("e", "Failed to create snapshot image")
                return None  # Failing to create thumbnail should not fail creation of UFP

            if snapshot:
                Logger.log("i", "Snapshot Found")

                # thumbnail = archive.getStream("/Metadata/thumbnail.png")

                thumbnail_buffer = QBuffer()
                thumbnail_buffer.open(QBuffer.ReadWrite)
                snapshot.save(thumbnail_buffer, "PNG")

                f = open('C:/Temp/Snapshot.png', 'wb')
                f.write(thumbnail_buffer.data())
                f.close()
                return thumbnail_buffer
            else:
                Logger.log("i", "No Snapshot Found")
                return None

                # thumbnail.write(thumbnail_buffer.data())

        except Exception:
            Logger.logException(
                "e", "Exception raised saving snapshot")
            return None

    def _getCuraMetadata(self):
        '''Returns meta data about cura and the plugin itself.'''
        data = dict()
        data["time_stamp"] = time.time()
        data["cura_version"] = self._application.getVersion()
        data["cura_build_type"] = ApplicationMetadata.CuraBuildType
        data["plugin_version"] = self.plugin_version

        return data

    def _getPrintTime(self):
        '''Returns the estimated print time in seconds.'''
        data = dict()
        print_information = self._application.getPrintInformation()
        data["estimated_print_time_seconds"] = int(
            print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))

        return data

    def _getPrintName(self):
        '''Returns the name of the Print Object.'''
        for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
            if node.callDecoration("isSliceable"):
                return node.getName()

        return ''

    def _getMaterialUsage(self):
        '''Returns a dictionary containing the material used in milligrams.'''
        print_information = self._application.getPrintInformation()

        data = dict()
        material_used_g = sum(print_information.materialWeights)
        material_used_mg = round(material_used_g * 1000)
        data["material_used_mg"] = material_used_mg

        return data

    def _generateNotes(self):
        data = dict()

        preferences = self._application.getInstance().getPreferences()
        setting_string = preferences.getValue("3d_print_log/logged_settings")
        logged_settings = set(setting_string.split(";"))

        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        notes = ''

        # Add Profile Name to notes if the user has it selected.
        include_profile_setting = preferences.getValue(
            "3d_print_log/include_profile_name")
        if (include_profile_setting):
            notes = notes + "Profile: " + \
                self._application.getMachineManager().activeQualityOrQualityChangesName + "\n\n"

        # Add Filament Names to notes if the user has it selected.
        include_filament_name = preferences.getValue(
            "3d_print_log/include_filament_name")
        if (include_filament_name):

            extruders = global_stack.extruderList
            extruders = sorted(
                extruders, key=lambda extruder: extruder.getMetaDataEntry("position"))

            materials = []
            # Loop through each extruder and get the filament name if that extruder is used.
            for extruder in extruders:
                extruder_position = int(
                    extruder.getMetaDataEntry("position", "0"))

                print_information = self._application.getPrintInformation()
                if len(print_information.materialLengths) > extruder_position:
                    materialUsed = print_information.materialLengths[extruder_position]

                    if (materialUsed is None or not (materialUsed > 0)):
                        continue

                    materials.append(extruder.material.getMetaData().get(
                        "brand", "") + " " + extruder.material.getMetaData().get("name", ""))

            if (len(materials) > 0):
                notes = notes + "Filament: " + ", ".join(materials) + "\n\n"

        # Add settings to the notes.
        notes = notes + "Settings:\n"

        # Grab an instance of our SettingDefinitions so we can loop over the settings while preserving their order
        settingDef = PrintLogSettingDefinitionsModel.PrintLogSettingDefinitionsModel()

        settingDef.id = "test"
        settingDef.containerId = global_stack.definition.id
        Logger.log("i", "Container ID %s", settingDef.containerId)
        settingDef.visibilityHandler = PrintLogSettingsVisibilityHandler.PrintLogSettingsVisibilityHandler()
        settingDef.showAll = True
        settingDef.showAncestors = True
        settingDef.expanded = ["*"]
        settingDef.exclude = ["machine_settings", "command_line_settings"]

        settingDef.forceUpdate()
        settingDef._updateVisibleRows()

        categoryData = dict()
        categoryString = ''
        currentCategory = None
        # Loop through the PrintLogSettingDefinitionsModel's rows
        for index in range(settingDef.rowCount()):
            modelIndex = settingDef.createIndex(index, 0)
            item = settingDef.data(modelIndex, settingDef.KeyRole)

            # if "type" is "category" then start a new dict.
            type = global_stack.getProperty(item, "type")
            if type.lower() == "category":
                if currentCategory is not None:
                    # If we have been adding to a current Category, save it and make a new dictionary
                    if (len(categoryData) > 0):
                        data[currentCategory] = categoryData

                        notes = notes + categoryString
                    categoryData = dict()

                currentCategory = global_stack.getProperty(item, "label")
                categoryString = currentCategory + "\n"

                continue

            # If the setting name is in our list of logged settings, then add it to the note.
            if (item in logged_settings):
                settingNote = self._buildSettingRow(item)
                categoryData[item] = settingNote
                categoryString = categoryString + "  " + settingNote + "\n"

        # Add the last category if any data exists for it:
        if (len(categoryData) > 0):
            notes = notes + categoryString

        return notes

    def _buildSettingRow(self, setting_name) -> str:
        '''Builds the string representation of a single setting, 
        taking into account if the setting is different between extruders.'''

        machine_manager = self._application.getMachineManager()
        global_stack = machine_manager.activeMachine

        # Get List of all extruders that used filament
        extruders = global_stack.extruderList
        extruders = sorted(
            extruders, key=lambda extruder: extruder.getMetaDataEntry("position"))

        # Get values for this setting for all extruders
        settingValues = collections.OrderedDict()
        for extruder in extruders:
            extruder_position = int(
                extruder.getMetaDataEntry("position", "0"))

            print_information = self._application.getPrintInformation()
            if len(print_information.materialLengths) > extruder_position:
                materialUsed = print_information.materialLengths[extruder_position]

                if (materialUsed is None or not (materialUsed > 0)):
                    continue

                value = extruder.getProperty(setting_name, "value")
                unit = extruder.getProperty(setting_name, "unit")

                result = str(value)

                if unit and not str(unit).isspace():
                    if (str(unit) in ["°C", "°F", "%"]):
                        result = result + str(unit)
                    else:
                        result = result + " " + str(unit)

                settingValues["Ex " + str(extruder_position + 1)] = result

        # If the values are all the same, just use the setting and format as:
        # Layer Height: 0.5mm
        areAllValuesTheSame = len(list(set(list(settingValues.values())))) == 1
        if (areAllValuesTheSame):
            label = global_stack.getProperty(setting_name, "label")
            value = list(settingValues.values())[0]

            return str(label) + ": " + str(value)

        # If the values are different, then combine them like:
        # Layer Height: 0.5 mm (Ex 1), 0.8mm (Ex 2)
        label = global_stack.getProperty(setting_name, "label")
        result = str(label) + ": "
        isFirst = True
        for setting in settingValues:
            if (not isFirst):
                result = result + ", "

            result = result + \
                settingValues[setting] + " (" + str(setting) + ")"

            isFirst = False

        return result
