import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import "qrc:/printerui/qml/X1Plus.js" as X1Plus

GridLayout {
    rowSpacing: 24
    columnSpacing: 12
    columns: 2
    Layout.fillWidth: true
    Layout.alignment: Qt.AlignLeft | Qt.AlignTop

    ZButton {
        text: qsTr("Test camera 1")
        Layout.columnSpan: 1
        Layout.alignment: Qt.AlignCenter
        textSize: 32
        paddingX: 20
        paddingY: 15
        checked: true
        enabled: !changes_pending
        
        onClicked: { X1Plus.Actions.execute({ "gpio": { "action": "pulse", "duration": "0.5", "gpio": { "function": "shutter", "pin": 3, "port": port }}}); }
    }

    ZButton {
        text: qsTr("Test camera 2")
        Layout.columnSpan: 1
        Layout.alignment: Qt.AlignCenter
        textSize: 32
        paddingX: 20
        paddingY: 15
        checked: true
        enabled: !changes_pending
        
        onClicked: { X1Plus.Actions.execute({ "gpio": { "action": "pulse", "duration": "0.5", "gpio": { "function": "shutter", "pin": 5, "port": port }}}); }
    }

    Text {
        visible: changes_pending
        
        font: Fonts.body_28
        Layout.alignment: Qt.AlignCenter
        color: Colors.warning
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.columnSpan: 2
        Layout.bottomMargin: 18

        text: qsTr("<b>Configuration must be saved to test module.</b>")
    }

}
