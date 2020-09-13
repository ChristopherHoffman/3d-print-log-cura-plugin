# Copyright (c) 2018 Ultimaker B.V.
# Uranium is released under the terms of the LGPLv3 or higher.

from UM.Application import Application
from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin
from UM.i18n import i18nCatalog
from .test import TestSliceInfo

catalog = i18nCatalog("uranium")


class SendTo3DPrintLog(OutputDevicePlugin):
    """Implements an OutputDevicePlugin that provides a single instance of LocalFileOutputDevice"""

    def __init__(self):
        super().__init__()

        Application.getInstance().getPreferences().addPreference(
            "hoffman_test_plugin/last_used_type", "")
        Application.getInstance().getPreferences().addPreference(
            "hoffman_test_plugin/dialog_save_path", "")

    def start(self):
        self.getOutputDeviceManager().addOutputDevice(TestSliceInfo())

    def stop(self):
        self.getOutputDeviceManager().removeOutputDevice("hoffman_test_plugin")
