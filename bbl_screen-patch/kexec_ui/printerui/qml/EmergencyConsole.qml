import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0
import DdsListener 1.0
import X1PlusNative 1.0

import "qrc:/uibase/qml/widgets"

import "settings"
import "."

Rectangle {
    id: screen
    width: 1280
    height: 720
    color: Colors.gray_500
    
    Text {
        id: titlelabel
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: 48
        anchors.leftMargin: 48
        anchors.right: parent.right
        font: Fonts.head_48
        color: Colors.brand
        text: "Emergency recovery console"
    }
    
    ZLineSplitter {
        id: splitter
        height: 2
        anchors.top: titlelabel.bottom
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.topMargin: 24
        padding: 15
        color: Colors.gray_300
    }
    
    property var recoveryStat: null

    Timer {
        /* This is super hokey, to allow a paint after we say 'unpacking
         * firmware bundle' but before we go to sleep for a while doing it. 
         */
        id: unpackTimer
        running: true
        repeat: false
        interval: 250
        onTriggered: {
            X1PlusNative.system(`/opt/kexec/start_recovery.sh &`);
        }
    }
    
    Timer {
        id: waitConsole
        running: true
        repeat: true
        interval: 250
        onTriggered: {
            let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/tmp/emergency_console.json";
            let xhr = new XMLHttpRequest();
            xhr.open("GET", path, /* async = */ false);
            xhr.send();
            if (xhr.status == 200) {
                waitConsole.running = false;
                recoveryStat = JSON.parse(xhr.response);
            }
        }
    }


    Item {
        id: body
        anchors.top: splitter.bottom
        anchors.topMargin: 24
        anchors.left: parent.left
        anchors.leftMargin: 48
        anchors.right: parent.right
        anchors.rightMargin: 48
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 48
        
        Item {
            id: lframe
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 16
            anchors.bottom: parent.bottom
            width: 400

            Text {
                id: descriptionText
                wrapMode: Text.WordWrap
                width: parent.width
                color: Colors.gray_100
                font: Fonts.body_28
                text: !recoveryStat ? "Starting emergency recovery console..."
                                    : ("Emergency recovery console is running.  You can access it in the following ways:"+
                                       (recoveryStat.ip ? `<br><br><b>SSH to x1plus@${recoveryStat.ip}.</b>  The password is ${recoveryStat.sshPassword}; your printer is connected to the Wi-Fi network \"${recoveryStat.wifiNetwork}\".` : "")+
                                       "<br><br><b>Connect a micro-USB cable to the AP board</b> and use ADB to connect."+
                                       "<br><br><b>Connect a UART to the AP board.</b>"+
                                       "<br><br><b>It is possible to do permanent, irreversible damage to your printer from a root console.  Do not enter commands unless you understand what you are typing.</b>"+
                                       "<br><br>To exit the emergency console, restart your printer.")
            }
        }
    }
}
