from . import PrintLogUploader


def getMetaData():
    return {}


def register(app):
    return {"extension": PrintLogUploader.PrintLogUploader()}
