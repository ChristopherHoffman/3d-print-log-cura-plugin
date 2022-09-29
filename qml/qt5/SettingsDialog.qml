import QtQuick 2.2
import QtQuick.Controls 1.2
import QtQuick.Window 2.2
import QtQuick.Layouts 1.1

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

    ColumnLayout
    {
        anchors.fill: parent

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

        UM.TooltipArea
        {
            width: childrenRect.width;
            height: childrenRect.height;

            text: "Include Snapshot of Model."

            CheckBox
            {
                id: includeSnapshotCheckbox

                checked: UM.Preferences.getValue("3d_print_log/include_snapshot")
                onClicked: UM.Preferences.setValue("3d_print_log/include_snapshot",  checked)

                text: "Include Model Snapshot"
            }
        }

        UM.TooltipArea
        {
            width: childrenRect.width;
            height: childrenRect.height;

            text: "Include object names, position, and scale information in the notes."

            UM.CheckBox
            {
                id: includeSnapshotCheckbox

                checked: UM.Preferences.getValue("3d_print_log/include_object_details")
                onClicked: UM.Preferences.setValue("3d_print_log/include_object_details",  checked)

                text: "Include Object Details in Notes"
            }
        }

        UM.TooltipArea
        {
            width: childrenRect.width;
            height: childrenRect.height;

            text: "Should we display a prompt after saving gcode?"

            GridLayout
            {
                id: interfaceGrid
                columns: 2
                width: parent.width

                Label
                {
                    id: promptSettingsLabel
                    text: "Log Print after Gcode Save"
                }

                

                ComboBox
                {
                    id: promptSettingsComboBox

                    textRole: "text"
                    model: ListModel
                    {
                        id: promptList

                        Component.onCompleted:
                        {
                            append({ text: "Always Ask", code: "always_ask" })
                            append({ text: "Always Send to 3D Print Log", code: "send_after_save" })
                            append({ text: "Never Send to 3D Print Log", code: "do_not_send" })
                        }
                    }

                    currentIndex: {
                        var code = UM.Preferences.getValue("3d_print_log/prompt_settings");
                        for(var i = 0; i < promptList.count; ++i)
                        {
                            if(model.get(i).code == code)
                            {
                                return i
                            }
                        }
                    }

                    onActivated:
                    {
                        if (model.get(index).code != "")
                        {
                            UM.Preferences.setValue("3d_print_log/prompt_settings", model.get(index).code);
                        }
                        else
                        {
                            var code = UM.Preferences.getValue("3d_print_log/prompt_settings");
                            for(var i = 0; i < promptList.count; ++i)
                            {
                                if(model.get(i).code == code)
                                {
                                    currentIndex = i
                                }
                            }
                        }
                    }
                }
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
            Layout.fillWidth: true

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
            Layout.fillHeight: true
            Layout.fillWidth: true

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
            anchors {
                rightMargin: UM.Theme.getSize("default_margin").width
            }
            
            text: catalog.i18nc("@action:button", "Reset To Defaults");
            onClicked: {
                UM.Preferences.resetPreference("3d_print_log/logged_settings")
                
                UM.Preferences.resetPreference("3d_print_log/include_profile_name")
                includeProfileNameCheckbox.checked = UM.Preferences.getValue("3d_print_log/include_profile_name")

                UM.Preferences.resetPreference("3d_print_log/include_filament_name")
                includeFilamentNameCheckbox.checked = UM.Preferences.getValue("3d_print_log/include_filament_name")

                UM.Preferences.resetPreference("3d_print_log/include_snapshot")
                includeSnapshotCheckbox.checked = UM.Preferences.getValue("3d_print_log/include_snapshot")

                UM.Preferences.resetPreference("3d_print_log/prompt_settings")
                promptSettingsComboBox.setCurrentIndex()

                settingsDialog.visible = false;
            }
        },
        Item
        {
            //: Spacer
            height: UM.Theme.getSize("default_margin").height
            width: UM.Theme.getSize("default_margin").width
        },
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
