import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

import UM as UM

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


