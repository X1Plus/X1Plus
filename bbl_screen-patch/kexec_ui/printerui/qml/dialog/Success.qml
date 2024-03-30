import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import X1PlusNative 1.0

Item {

    property alias name: textConfirm.objectName
    property string title
    property alias text: textContent.text
    property alias textFont: textContent.font
    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "reboot"; title: qsTr("Reboot")
            isDefault: true
            onClicked: function() { X1PlusNative.system("echo b > /proc/sysrq-trigger"); }
        }
    }
    property bool finished: false
    property var paddingBottom: 50

    function buttonClicked(index) {
        if (callback)
            callback(index)
    }

    id: textConfirm
    width: 650
    height: textContent.contentHeight
    objectName: "got it"

    Text {
        id: textContent
        width: parent.width
        font: Fonts.body_30
        color: Colors.gray_100
        wrapMode: Text.Wrap
        text: qsTr("<center><b>Success!</b></center><br><br>X1Plus has been successfully installed on your printer.  Leave the SD card inserted and restart your printer to enjoy your new custom firmware!")
    }
}
