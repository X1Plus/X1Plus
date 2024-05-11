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
    property var otaFlag:  X1PlusNative.getenv("X1P_OTA"); //name .x1p file in /mnt/sdcard/ (filename only)
    property int countdown: 10
    property bool finished: false
    property var paddingBottom: 50

    function buttonClicked(index) {
        if (callback)
            callback(index)
    }
    Timer {
        id: timer
        interval: 1000 // Check every second
        repeat: true // Repeat every second
        running: otaFlag !== "" && !finished
        onTriggered: {
            if (countdown > 0) {
                countdown--;
            } else {
                X1PlusNative.system("echo b > /proc/sysrq-trigger");
                finished = true;
                timer.stop();
            }
        }
    }
    
   property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "reboot"
            title: countdown > 0 ? qsTr("Reboot in ") + countdown + qsTr(" seconds") : qsTr("Reboot Now")
            isDefault: true
            onClicked: {
                X1PlusNative.system("echo b > /proc/sysrq-trigger");
            }
        }
    }

    Text {
        id: textContent
        anchors.fill: parent
        font: Fonts.body_30
        color: Colors.gray_100
        wrapMode: Text.Wrap
        text: qsTr("<center><b>Success!</b></center><br><br>X1Plus has been successfully installed on your printer.  Leave the SD card inserted and restart your printer to enjoy your new custom firmware!")
    }
}