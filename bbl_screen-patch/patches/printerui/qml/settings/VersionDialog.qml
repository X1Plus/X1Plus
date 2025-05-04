import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import "../dialog"

Item {
    property alias name: textConfirm.objectName
    property var modelData: ({}) /* friendly, bambu, cfw, icon */
    property var cfwVersion: ({}) /* from cfwversions.json: version, ... */
    property var mappedData: ({}) /* hw_ver, sn, sw_ver */
    property var isHw: (mappedData.sn && mappedData.sn != "" && mappedData.hw_ver && mappedData.hw_ver != "")
    property var needsUpdate: modelData.bambu == "filament" ? mappedData.sw_ver != "Custom" && mappedData.sw_ver < cfwVersion.version :
                              (!cfwVersion.invalid && mappedData.sn != "N/A" && mappedData.sw_ver.split("/")[0] != cfwVersion.version)
    property var sw_ver_text: modelData.bambu == "filament" && mappedData.sw_ver == "Custom" ? qsTr("Custom") :
                              modelData.bambu == "filament" && mappedData.sw_ver == "" ? qsTr("Not installed") :
                              mappedData.sw_ver.split("/")[0]
    
    property var noUpgrade_messages: ({
        "COPY_NEW_X1P": QT_TR_NOOP("To install a new version of the custom firmware, copy the new x1p file to the root of the SD card, power cycle the printer, and select the installer at startup time."),
        "WRONG_BASE_VERSION": QT_TR_NOOP("This custom firmware has been loaded on top of the wrong Bambu Lab base firmware version.  Printing may not be reliable.  Reinstall the custom firmware on the SD card."),
    })

    property var dialogName_messages: ({
        "X1Plus firmware": QT_TR_NOOP("X1Plus Firmware"),
        "Bambu Lab base firmware": QT_TR_NOOP("Bambu Lab base firmware"),
    })

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "do_install"; title: qsTr("Install %1").arg(cfwVersion.version)
            isDefault: defaultButton == 0
            keepDialog: true
            onClicked: {
                dialogStack.pop();
                dialogStack.popupDialog('../settings/UpgradeDialog', {
                    module: mappedData.name,
                    friendly: modelData.friendly,
                    version: cfwVersion.version,
                    url: cfwVersion.paths[mappedData.hw_ver.toLowerCase()]['url'],
                    md5: cfwVersion.paths[mappedData.hw_ver.toLowerCase()]['md5'],
                })
            }
            visible: needsUpdate && !cfwVersion.noUpgrade
        }
        DialogButtonItem {
            name: "no"; title: qsTr("Return")
            isDefault: defaultButton == 1
            onClicked: { ; }
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
            source: modelData.icon
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
                text: cfwVersion.dialogName ? qsTr(dialogName_messages[cfwVersion.dialogName]) : modelData.friendly
            }

            Text {
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: isHw
                text: qsTr("<b>Serial number</b>: %1").arg(mappedData.sn)
            }

            Text {
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: isHw
                text: qsTr("<b>Hardware revision</b>: %1").arg(mappedData.hw_ver)
            }
            
            
            Text {
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                Layout.columnSpan: 2
                text: qsTr("<b>Firmware version</b>: %1").arg(sw_ver_text) +
                    (needsUpdate ? qsTr(" (<font color='#ff6f00'><i>recommended: %1</i></font>)").arg(cfwVersion.version.split("/")[0]) : "")
            }
            
            Text {
                Layout.fillWidth: true
                Layout.topMargin: 18
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                Layout.columnSpan: 2
                text: !needsUpdate && !cfwVersion.alwaysNoUpgrade 
                    ? qsTr("This component has the recommended firmware version installed.") 
                    : (cfwVersion.noUpgrade
                        ? qsTr(noUpgrade_messages[cfwVersion.noUpgrade])
                        : qsTr("This component's firmware version does not match the running system firmware version. Printing may not be reliable. Install new firmware now?"))
            }
        }
    }
}
