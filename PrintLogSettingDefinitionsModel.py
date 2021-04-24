from UM.Settings.Models.SettingDefinitionsModel import SettingDefinitionsModel


class PrintLogSettingDefinitionsModel(SettingDefinitionsModel):

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

    def _isDefinitionVisible(self, definition, **kwargs):
        return super()._isDefinitionVisible(definition, **kwargs)
