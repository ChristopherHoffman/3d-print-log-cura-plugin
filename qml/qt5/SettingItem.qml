import QtQuick 2.1
import QtQuick.Layouts 1.1
import QtQuick.Controls 1.1

import UM 1.2 as UM

UM.TooltipArea
{
    x: model.depth * UM.Theme.getSize("default_margin").width;
    text: model.description;

    width: childrenRect.width;
    height: childrenRect.height;

    CheckBox
    {
        id: check

        text: definition.label
        checked: definition.visible;

        onClicked:
        {
            definitionsModel.visibilityHandler.setSettingVisibility(model.key, checked);
        }
    }
}


