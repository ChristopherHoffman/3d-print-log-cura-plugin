// Copyright (c) 2019 fieldOfView
// The MaterialSettingsPlugin is released under the terms of the AGPLv3 or higher.

import QtQuick 2.2
import QtQuick.Controls 1.2
import QtQuick.Controls.Styles 1.2
import QtQuick.Window 2.2

import UM 1.2 as UM
import Cura 1.0 as Cura
import PrintLogUploader 1.0 as PrintLogUploader

UM.Dialog {
    id: settingsDialog

    title: catalog.i18nc("@title:window", "Select Settings to Log")
    width: screenScaleFactor * 360

    onVisibilityChanged:
    {
        if(visible)
        {
            updateFilter()
        }
    }

    function updateFilter()
    {
        var new_filter = {};

        if(filterInput.text != "")
        {
            new_filter["i18n_label"] = "*" + filterInput.text;
        }

        listview.model.filter = new_filter;
    }

    Column
    {
        width: parent.width
        height: parent.height

        Label
        {
            font.bold: true
            text: "General"
        }

        UM.TooltipArea
        {
            width: childrenRect.width;
            height: childrenRect.height;

            text: "Include profile name in the Notes field."

            CheckBox
            {
                id: includeProfileNameCheckbox

                checked: UM.Preferences.getValue("3d_print_log/include_profile_name")
                onClicked: UM.Preferences.setValue("3d_print_log/include_profile_name", checked)

                text: "Include Profile Name"
            }
        }


        UM.TooltipArea
        {
            width: childrenRect.width;
            height: childrenRect.height;

            text: "Include filament/material name in the Notes field."

            CheckBox
            {
                id: includeFilamentNameCheckbox

                checked: UM.Preferences.getValue("3d_print_log/include_filament_name")
                onClicked: UM.Preferences.setValue("3d_print_log/include_filament_name",  checked)

                text: "Include Filament Name"
            }
        }

        Item
        {
            //: Spacer
            height: UM.Theme.getSize("default_margin").height
            width: UM.Theme.getSize("default_margin").width
        }

        Label
        {
            id: settingLabel
            font.bold: true
            text: "Settings"
        }

        Row {
            id: settingSearchRow
            width: parent.width

            TextField {

                id: filterInput
                width: settingSearchRow.width - searchSpacer.width - toggleShowAll.width
                placeholderText: catalog.i18nc("@label:textbox", "Filter...");

                onTextChanged: settingsDialog.updateFilter()
            }

            Item
            {
                id: searchSpacer
                //: Spacer
                height: UM.Theme.getSize("default_margin").height
                width: UM.Theme.getSize("default_margin").width
            }

            CheckBox
            {
                id: toggleShowAll
                
                text: catalog.i18nc("@label:checkbox", "Show all")
                checked: listview.model.showAll
                onClicked:
                {
                    listview.model.showAll = checked;
                }
            }
        }

        ScrollView
        {
            id: scrollView


            anchors
            {

                left: parent.left;
                right: parent.right;

            }
            ListView
            {
                id:listview
                model: PrintLogUploader.PrintLogSettingDefinitionsModel
                {
                    id: definitionsModel;
                    containerId: Cura.MachineManager.activeMachine.definition.id
                    visibilityHandler: Cura.PrintLogSettingsVisibilityHandler {}
                    showAll: true
                    showAncestors: true
                    expanded: [ "*" ]
                    exclude: [ "machine_settings", "command_line_settings" ]
                }
                delegate:Loader
                {
                    id: loader

                    width: parent.width
                    height: model.type != undefined ? UM.Theme.getSize("section").height : 0;

                    property var definition: model
                    property var settingDefinitionsModel: definitionsModel

                    asynchronous: true
                    source:
                    {
                        switch(model.type)
                        {
                            case "category":
                                return "SettingCategory.qml"
                            default:
                                return "SettingItem.qml"
                        }
                    }
                }
                Component.onCompleted: settingsDialog.updateFilter()
            }
        }
    }
    

    rightButtons: [
        Button {
            text: catalog.i18nc("@action:button", "Close");
            onClicked: {
                settingsDialog.visible = false;
            }
        }
    ]

    Item
    {
        UM.I18nCatalog { id: catalog; name: "cura"; }
    }
}
