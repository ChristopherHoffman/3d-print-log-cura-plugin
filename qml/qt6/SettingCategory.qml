
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import UM as UM

import ".."

Button {
    id: base;

    background: Item { }
    label: Row
    {
        spacing: UM.Theme.getSize("default_lining").width

        UM.ColorImage
        {
            anchors.verticalCenter: parent.verticalCenter
            height: (label.height / 2) | 0
            width: height
            source: control.checked ? UM.Theme.getIcon("arrow_bottom") : UM.Theme.getIcon("arrow_right");
            color: control.hovered ? palette.highlight : palette.buttonText
        }
        UM.ColorImage
        {
            anchors.verticalCenter: parent.verticalCenter
            height: label.height
            width: height
            source: control.iconSource
            color: control.hovered ? palette.highlight : palette.buttonText
        }
        Label
        {
            id: label
            anchors.verticalCenter: parent.verticalCenter
            text: control.text
            color: control.hovered ? palette.highlight : palette.buttonText
            font.bold: true
        }

        SystemPalette { id: palette }
    }
    

    signal showTooltip(string text);
    signal hideTooltip();
    signal contextMenuRequested()

    text: definition.label
    iconSource: UM.Theme.getIcon("arrow_bottom")

    checkable: true
    checked: definition.expanded

    onClicked: definition.expanded ? settingDefinitionsModel.collapse(definition.key) : settingDefinitionsModel.expandRecursive(definition.key)
}
