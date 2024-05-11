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
    property int countdown: (X1PlusNative.getenv("KEXEC_LAUNCH_INSTALLER") !== "") ? 15 : 0 
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
        running: !finished
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
            title: countdown > 0 ? qsTr("Reboot in ") + countdown + qsTr(" seconds") : qsTr("Rebooting..")
            isDefault: true
            onClicked: {
                doReboot();
            }
        }
    }
    //Minor regression from 1.1: 
    //This dialog only displays after installing for the first time, and when it does, it will reboot after 15 seconds. 
    //This dialog provides post-install instructions important for new user, but after this the dialog is skipped. If we
    //want to change this, it seems we need to come up with a new dialog message with general install info 
    Text {
        id: textContent
        anchors.fill: parent
        font: Fonts.body_30
        color: Colors.gray_100
        wrapMode: Text.Wrap
        text: qsTr("<center><b>Success!</b></center><br><br>X1Plus has been successfully installed on your printer.  Leave the SD card inserted and restart your printer to enjoy your new custom firmware!")
    }
}