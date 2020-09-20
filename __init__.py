# Copyright (c) 2015 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.

from . import PrintLogUploader


def getMetaData():
    return {}


def register(app):
    return {"extension": PrintLogUploader.PrintLogUploader()}
