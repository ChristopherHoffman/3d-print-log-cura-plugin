from . import PrintLogUploader
from . import PrintLogSettingDefinitionsModel

USE_QT5 = False
try:
    from PyQt6.QtQml import qmlRegisterType
except ImportError:
    from PyQt5.QtQml import qmlRegisterType
    USE_QT5 = True


def getMetaData():
    return {}


def register(app):
    qmlRegisterType(PrintLogSettingDefinitionsModel.PrintLogSettingDefinitionsModel,
                    "PrintLogUploader", 1, 0, "PrintLogSettingDefinitionsModel")

    return {"extension": PrintLogUploader.PrintLogUploader()}
