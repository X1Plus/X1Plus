import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import "qrc:/printerui/qml/X1Plus.js" as X1Plus

ColumnLayout {
    spacing: 24
    Layout.fillWidth: true
    Layout.alignment: Qt.AlignLeft | Qt.AlignTop

    LedConfig {
        Layout.fillWidth: true
    }
    
    ZButton {
        text: qsTr("Test buzzer")
        Layout.alignment: Qt.AlignCenter
        textSize: 32
        paddingX: 20
        paddingY: 15
        checked: true
        enabled: !changes_pending
        
        onClicked: { X1Plus.Actions.execute({ "gpio": { "action": "pulse", "duration": "0.5", "gpio": { "function": "buzzer", "port": port }}}); }
    }

    Text {
        visible: changes_pending
        
        font: Fonts.body_28
        Layout.alignment: Qt.AlignCenter
        color: Colors.warning
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.bottomMargin: 18

        text: qsTr("<b>Configuration must be saved to test module.</b>")
    }
}
