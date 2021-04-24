from UM.Settings.Models.SettingVisibilityHandler import SettingVisibilityHandler
from UM.Application import Application

from UM.FlameProfiler import pyqtSlot


class PrintLogSettingsVisibilityHandler(SettingVisibilityHandler):
    '''Create a custom visibility handler so we can hide/show settings in the dialogs.'''

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self._preferences = Application.getInstance().getPreferences()
        self._preferences.preferenceChanged.connect(self._onPreferencesChanged)

        self._onPreferencesChanged("3d_print_log/logged_settings")
        self.visibilityChanged.connect(self._updatePreference)

    def _onPreferencesChanged(self, name: str) -> None:
        if name != "3d_print_log/logged_settings":
            return

        visibility_string = self._preferences.getValue(
            "3d_print_log/logged_settings")
        if not visibility_string:
            self._preferences.resetPreference(
                "3d_print_log/logged_settings")
            return

        material_settings = set(visibility_string.split(";"))
        if material_settings != self.getVisible():
            self.setVisible(material_settings)

    def _updatePreference(self) -> None:
        visibility_string = ";".join(self.getVisible())
        self._preferences.setValue(
            "3d_print_log/logged_settings", visibility_string)

    # Set a single SettingDefinition's visible state
    @pyqtSlot(str, bool)
    def setSettingVisibility(self, key: str, visible: bool) -> None:
        visible_settings = self.getVisible()
        if visible:
            visible_settings.add(key)
        else:
            try:
                visible_settings.remove(key)
            except KeyError:
                pass

        self.setVisible(visible_settings)
