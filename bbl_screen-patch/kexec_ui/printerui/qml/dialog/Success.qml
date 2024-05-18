import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import X1PlusNative 1.0

Item {
    id: textConfirm
    width: 650
    height: textContent.contentHeight
    objectName: "got it"
    property alias name: textConfirm.objectName
    property string title
    property alias text: textContent.text
    property alias textFont: textContent.font
    property int countdown: 10
    property bool shouldCountdown: (X1PlusNative.getenv("X1P_OTA") || "") != ""
    property bool finished: false
    property var paddingBottom: 50

    function buttonClicked(index) {
        if (callback)
            callback(index)
    }
    function doReboot(){
        finished = true;
        X1PlusNative.system("echo b > /proc/sysrq-trigger");
    }
    
    Timer {
        id: timer
        interval: 1000
        repeat: true
        running: !finished && shouldCountdown
        onTriggered: {
            countdown--;
            if (countdown <= 0) {
                doReboot();
            }
        }
    }
    
   property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "reboot"
            title: finished ? qsTr("Rebooting...") :
                   shouldCountdown ? qsTr("Rebooting in %1 seconds").arg(countdown)
                                   : "Reboot"
            isDefault: true
            onClicked: {
                doReboot();
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
