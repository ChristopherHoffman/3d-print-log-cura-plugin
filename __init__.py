# Copyright (c) 2015 Ultimaker B.V.
# Cura is released under the terms of the LGPLv3 or higher.

from . import test


def getMetaData():
    return {}


def register(app):
    return {"extension": test.TestSliceInfo()}
