import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import "../dialog"

import "../X1Plus.js" as X1Plus

Item {
    property alias name: textConfirm.objectName
    property var currentVersion: screenSaver.cfwVersions['cfw']['version']
    property var ota: X1Plus.OTA.status()
    property var otaEnabled: !!X1Plus.Settings.get("ota.enabled", false)
    property var downloadBaseFirmware: true /* wire up to switch */
    property var otaBusy: ota.status != 'IDLE' && ota.status != 'DISABLED'
    property var progressString: `${(ota.download.bytes / 1048576).toFixed(2)} MB / ${(ota.download.bytes_total / 1048576).toFixed(2)} MB`

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "download"; title: ota.ota_is_downloaded ? qsTr("Download base firmware") : qsTr("Download update")
            isDefault: defaultButton == 0
            keepDialog: true
            onClicked: {
                X1Plus.OTA.download(downloadBaseFirmware);
            }
            visible: otaEnabled && !otaBusy && ota.ota_available && (!ota.ota_is_downloaded || (downloadBaseFirmware && !ota.ota_base_is_downloaded))
        }
        DialogButtonItem {
            name: "install"; title: qsTr("Install update")
            isDefault: defaultButton == 1
            keepDialog: true
            onClicked: {
                var rv = X1Plus.OTA.update();
                if (rv.status != 'failed') {
                    otaBusy = true;
                }
            }
            visible: otaEnabled && !otaBusy && ota.ota_available && ota.ota_is_downloaded
        }
        DialogButtonItem {
            name: "no"; title: qsTr("Return")
            isDefault: defaultButton == 2
            onClicked: { ; }
            visible: !otaBusy
        }
    }
    property bool finished: false

    id: textConfirm
    width: 960
    height: layout.height
    
    RowLayout {
        id: layout
        width: 960
        spacing: 0
        
        Image {
            id: moduleIcon
            Layout.preferredWidth: 128
            Layout.preferredHeight: 128
            Layout.rightMargin: 24
            Layout.alignment: Qt.AlignTop | Qt.AlignLeft
            fillMode: Image.PreserveAspectFit
            source: "../../icon/components/cfw.png"
        }
        
        GridLayout {
            rowSpacing: 6
            columnSpacing: 12
            columns: 2
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignLeft | Qt.AlignTop
            Layout.maximumWidth: 1000
            
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.bottomMargin: 18
                font: Fonts.body_36
                color: Colors.gray_100
                wrapMode: Text.Wrap
                text: "X1Plus updates"
            }

            
            Text {
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                Layout.columnSpan: 2
                Layout.bottomMargin: 16
                text: qsTr("<b>Current X1Plus version</b>: %1").arg(currentVersion)
            }
            
            Text {
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                text: otaEnabled ? qsTr("Checking for X1Plus updates is enabled.") : qsTr("Checking for X1Plus updates is disabled.")
                Layout.columnSpan: otaBusy ? 2 : 1
            }
            
            ZSwitchButton {
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                visible: !otaBusy
                dynamicChecked: otaEnabled
                onToggled: {
                    X1Plus.Settings.put("ota.enabled", checked)
                }
            }

            ZLineSplitter {
                Layout.fillWidth: true
                Layout.columnSpan: 2
                Layout.topMargin: 20
                Layout.bottomMargin: 10
                alignment: Qt.AlignTop
                padding: 24
                color: Colors.gray_300
                visible: otaEnabled
            }
            
            /*** Last update check ***/
            
            Text {
                text: qsTr("<i>Checking for updates...</i>")
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: otaEnabled && ota.status == 'CHECKING_OTA'
            }
            
            Text {
                text: qsTr("<b>Last checked for updates</b>: %1").arg(new Date(ota.last_checked * 1000).toLocaleString(undefined, {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}))
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: otaEnabled && ota.status != 'CHECKING_OTA'
            }
            
            ZButton {
                id: refreshBtn
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                width: 46
                height: width
                radius: width / 2
                type: ZButtonAppearance.Secondary
                iconPosition: ZButtonAppearance.Center
                paddingX: 0
                iconSize: 46
                textColor: StateColors.get("gray_100")
                icon: "../../icon/refresh.svg"
                visible: otaEnabled
                onClicked: {
                    X1Plus.OTA.checkNow()
                }
                
                RotationAnimation {
                    id: rotationId
                    target: refreshBtn.iconItem
                    property: "rotation"
                    loops: Animation.Infinite
                    alwaysRunToEnd: true
                    duration: 1000
                    from: 0
                    to: 360
                    running: ota.status == 'CHECKING_OTA'
                }
            }
            
            Text {
                text: qsTr("<i>Most recent check for updates failed.  Check your network connection.</i>")
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: otaEnabled && ota.err_on_last_check
                Layout.columnSpan: 2
            }
            
            /*** New OTA available ***/
            
            Text {
                text: qsTr("You are running the newest version of X1Plus.")
                font: Fonts.body_26
                color: Colors.gray_200
                Layout.topMargin: 10
                wrapMode: Text.Wrap
                visible: otaEnabled && !ota.ota_available
                Layout.columnSpan: 2
            }
            
            Text {
                text: qsTr("<b>New X1Plus version %1</b> is available!").arg((ota.ota_info || {}).cfwVersion)
                font: Fonts.body_26
                color: Colors.gray_200
                Layout.topMargin: 10
                wrapMode: Text.Wrap
                visible: otaEnabled && ota.ota_available
                Layout.columnSpan: 2
            }
            
            
            Text {
                text: ota.status == 'DOWNLOADING_X1P' ? qsTr("X1Plus update download in progress (%1).").arg(progressString) :
                      ota.ota_is_downloaded ?
                        qsTr("X1Plus update %1download complete%2.").arg('<b><font color="#20ce62">').arg('</font></b>') :
                        qsTr("X1Plus update has not been downloaded.")
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                Layout.columnSpan: 2
                visible: otaEnabled && ota.ota_available
            }

            Text {
                text: ota.status == 'DOWNLOADING_BASE' ? qsTr("Base firmware download in progress (%1).").arg(progressString) :
                      ota.ota_base_is_downloaded ?
                          qsTr("Base firmware %1download complete%2.").arg('<b><font color="#20ce62">').arg('</font></b>') :
                        downloadBaseFirmware ? qsTr("Base firmware has not been downloaded, but downloading it from Bambu Lab servers is enabled.") :
                                               qsTr("Base firmware has not been downloaded, and downloading it is disabled.")
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                Layout.columnSpan: (ota.ota_base_is_downloaded || ota.status == 'DOWNLOADING_BASE') ? 2 : 1
                visible: otaEnabled && ota.ota_available
                Layout.fillWidth: true
            }

            ZSwitchButton {
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                dynamicChecked: downloadBaseFirmware
                onToggled: {
                    downloadBaseFirmware = checked
                }
                visible: otaEnabled && ota.ota_available && !(ota.ota_base_is_downloaded || ota.status == 'DOWNLOADING_BASE')
            }
            
            Text {
                text: qsTr("<i>Last download failed: %1</i>").arg(ota.download.last_error)
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                Layout.columnSpan: 2
                visible: otaEnabled && ota.ota_available && ota.download.last_error
                Layout.fillWidth: true
            }
        }
    }
}
