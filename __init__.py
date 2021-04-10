from . import PrintLogUploader
from . import PrintLogSettingDefinitionsModel

from PyQt5.QtQml import qmlRegisterType


def getMetaData():
    return {}


def register(app):
    qmlRegisterType(PrintLogSettingDefinitionsModel.PrintLogSettingDefinitionsModel,
                    "PrintLogUploader", 1, 0, "PrintLogSettingDefinitionsModel")

    return {"extension": PrintLogUploader.PrintLogUploader()}
