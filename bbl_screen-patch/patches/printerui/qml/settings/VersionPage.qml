import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0

import "qrc:/uibase/qml/widgets"
import ".."
import "../X1Plus.js" as X1Plus

Item {
    property var modules: X1Plus.DDS.versions()
    property var mapping: ([
        /* dummy %1s for hw_ver arg */
        { "friendly": QT_TR_NOOP("X1Plus version%1"), "cfw": "cfw", "icon": "../../icon/components/cfw.png" },
        { "friendly": QT_TR_NOOP("Base firmware version%1"), "cfw": "ota", "icon": "../../icon/components/mainfw.png" },
        { "friendly": QT_TR_NOOP("AP board%1"), "bambu": "ap", "cfw": "rv1126", "icon": "../../icon/components/ap-board.svg" },
        { "friendly": QT_TR_NOOP("MC board%1"), "bambu": "mc", "cfw": "mc", "icon": "../../icon/components/mc-board.svg" },
        { "friendly": QT_TR_NOOP("Toolhead%1"), "bambu": "th", "cfw": "th", "icon": "../../icon/components/th.svg" },
        { "friendly": QT_TR_NOOP("Filament database%1"), "bambu": "filament", "cfw": "filament", "icon": "../../icon/components/ams.svg" }, // XXX: do icon
        { "friendly": QT_TR_NOOP("AMS hub%1"), "bambu": "ahb", "cfw": "ahb", "icon": "../../icon/components/ahb.svg" },
        { "friendly": QT_TR_NOOP("%1 #1"), "bambu": "ams/0", "cfw": "ams", "icon": "../../icon/components/ams.svg" },
        { "friendly": QT_TR_NOOP("%1 #2"), "bambu": "ams/1", "cfw": "ams", "icon": "../../icon/components/ams.svg" },
        { "friendly": QT_TR_NOOP("%1 #3"), "bambu": "ams/2", "cfw": "ams", "icon": "../../icon/components/ams.svg" },
        { "friendly": QT_TR_NOOP("%1 #4"), "bambu": "ams/3", "cfw": "ams", "icon": "../../icon/components/ams.svg" }
        // EXT board is coming soon
        // chamber heater is coming soon
        // investigate: DeviceManager.allModules; allModules[DeviceManager.build.product]
    ])
    property var cfwVersions: screenSaver.cfwVersions

    function decode_hw_arg(hw_ver) {
        if (!hw_ver)
            return "";
        if (hw_ver.slice(0,3) == "N3F")
            return "AMS 2 Pro";
        if (hw_ver.slice(0,3) == "N3S")
            return "AMS HT";
        if (hw_ver.slice(0,3) == "AMS")
            return "AMS";
        return "";
    }

    Component.onCompleted: {
        X1Plus.DDS.requestVersions();
    }

    MarginPanel {
        id: title
        height: 68 + 39 + 30
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        radius: 0
        color: "#393938"

        Item {
            id: titlePanel
            height: 68
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 39

            Image {
                id: brandImage
                x: 28
                width: titlePanel.height
                height: brandImage.width
                source: "../../icon/brand.svg"
            }

            Text {
                id: titleName
                anchors.left: brandImage.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                color: Colors.gray_200
                font: Fonts.body_36
                text: qsTr("Firmware version")
            }

            ZButton {
                id: returnBtn
                anchors.right: parent.right
                anchors.rightMargin: 28
                anchors.top: parent.top
                anchors.topMargin: 6
                checked: false
                text: qsTr("Return")
                onClicked: { parent.parent.parent.parent.pop() }
            }
        }
    }

    MarginPanel {
        id: infosPanel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        leftMargin: 26
        rightMargin: 26
        bottomMargin: 26
        radius: 15
        color: Colors.gray_600

        ListView {
            id: infoList
            clip: true
            anchors.fill: parent
            anchors.rightMargin: 10
            boundsBehavior: Flickable.StopAtBounds
            interactive: true
            ScrollBar.vertical: ScrollBar {
                policy: infoList.contentHeight > infoList.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                interactive: true
            }
            model: mapping.filter(el => !el.bambu || modules.find(el2 => el.bambu == el2.name))
            delegate: infoComp
        }
    }

    Component {
        id: infoComp
        
        Rectangle {
            property var cfwVersion: (cfwVersions[modelData.cfw] ? cfwVersions[modelData.cfw] : { "version": "unknown", "invalid": true })
            property var mappedData: (modelData.bambu === undefined ?
                                        {"sw_ver": cfwVersion.version, "sn": "", "hw_ver": "" } :
                                        modules.find(el => modelData.bambu == el.name))
            property var needsUpdate: modelData.bambu == "filament" ? mappedData.sw_ver != "Custom" && mappedData.sw_ver < cfwVersion.version :
                                      modelData.cfw == 'cfw' ? X1Plus.OTA.status()['ota_available'] : 
                                      (!cfwVersion.invalid &&
                                       (!mappedData.hw_ver || cfwVersion.paths[mappedData.hw_ver.toLowerCase()] !== undefined) &&
                                       mappedData.sn != "N/A" && mappedData.sw_ver.split("/")[0] != cfwVersion.version)
            
            // a few translatable overrides go here...  annoyingly, this
            // gets replicated in VersionDialog, but is there a better way
            // given what we already have at this point?
            property var sw_ver_text: modelData.bambu == "filament" && mappedData.sw_ver == "Custom" ? qsTr("Custom") :
                                      modelData.bambu == "filament" && mappedData.sw_ver == "" ? qsTr("Not installed") :
                                      mappedData.sw_ver.split("/")[0]
            width: ListView.view.width
            height: 81
            color: modelData.onClicked === undefined ? "transparent" : backColor.color
            radius: 15

            ZLineSplitter {
                alignment: Qt.AlignTop
                padding: 23
                color: "#606060"
                visible: index > 0
            }

            Item {
                height: parent.height
                anchors.left: parent.left
                anchors.leftMargin: 36
                anchors.right: parent.right
                anchors.rightMargin: 36

                Rectangle {
                    width: parent.width
                    height: 1
                    anchors.bottom: parent.bottom
                    color: "#606060"
                    visible: index + 1 < modules.length
                }

                Image {
                    id: moduleIcon
                    anchors.verticalCenter: parent.verticalCenter
                    fillMode: Image.PreserveAspectFit
                    width: height
                    height: parent.height - 13
                    source: modelData.icon
                }

                Text {
                    id: infoListTitle
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: moduleIcon.right
                    anchors.leftMargin: 10
                    color: Colors.gray_200
                    font: Fonts.body_30
                    text: qsTr(modelData.friendly).arg(decode_hw_arg(mappedData.hw_ver))
                }
                
                Text {
                    id: infoSN
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: infoListTitle.right
                    anchors.leftMargin: 10
                    color: Colors.gray_200
                    font: Fonts.body_26
                    text: "(" + mappedData.sn + ")"
                    visible: mappedData.sn != ""
                }

                Text {
                    id: valueText
                    width: Math.min((parent.width - moduleIcon.width - 10 - 16 - infoSN.contentWidth - infoListTitle.contentWidth - (menuImage.visible ? menuImage.width : 0) - 22), implicitWidth)
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: menuImage.visible ? menuImage.left : parent.right
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                    color: needsUpdate ? Colors.warning : Colors.gray_400
                    font: Fonts.body_26
                    text: sw_ver_text
                }

                Image {
                    id: menuImage
                    width: height
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    fillMode: Image.Pad
                    horizontalAlignment: Qt.AlignRight
                    source: "../../icon/right.svg"
                }
            }

            TapHandler {
                onTapped: {
                    console.log(modelData.bambu);
                    if (modelData.cfw == 'cfw') {
                        dialogStack.popupDialog('../settings/X1PlusOTADialog', {});
                    } else {
                        dialogStack.popupDialog('../settings/VersionDialog', { modelData: modelData, mappedData: mappedData, cfwVersion: cfwVersion, hw_arg: decode_hw_arg(mappedData.hw_ver)});
                    }
                }
            }

            StateColorHandler {
                id: backColor
                stateColor: StateColors.get("transparent_pressed")
            }
        }

    }

}
