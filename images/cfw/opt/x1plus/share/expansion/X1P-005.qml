import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"

GridLayout {
    rowSpacing: 24
    columnSpacing: 12
    columns: 2
    Layout.fillWidth: true
    Layout.alignment: Qt.AlignLeft | Qt.AlignTop

    Text {
        font: Fonts.body_26
        color: Colors.gray_200
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.columnSpan: 2

        text: qsTr("<i>Placeholder: LED configuration</i>")
    }
    
    
    ZButton {
        text: qsTr("Test buzzer")
        Layout.columnSpan: 2
        Layout.alignment: Qt.AlignCenter
        textSize: 32
        paddingX: 20
        paddingY: 15
        checked: true
        enabled: !changes_pending
        
        onClicked: { /* XXX */; }
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
