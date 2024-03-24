import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import DdsListener 1.0
import "qrc:/uibase/qml/widgets"

Item {
    property alias name: textConfirm.objectName
    /* Replicated in BootOptionsPage.qml; keep this in sync if you change this (or, really, refactor it then). */
    property var hasSdCard: (function () {
        let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/boot.conf";
        let xhr = new XMLHttpRequest();
        xhr.open("GET", path, /* async = */ false);
        xhr.send();
        return xhr.status == 200;
    }())
    property var countdown: 10

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "yes_confirm"; title: qsTr("Start from SD card")
            isDefault: defaultButton == 0
            onClicked: { countdown = 0 }
            visible: hasSdCard && countdown > 0
        }
        DialogButtonItem {
            name: "no"; title: qsTr("Startup options...")
            isDefault: defaultButton == 1
            onClicked: { timer.stop(); dialogStack.replace("../BootOptionsPage.qml", {hasSdCard: hasSdCard}); }
            visible: countdown > 0
        }
    }
    property bool finished: false

    Timer {
        id: timer
        running: hasSdCard
        interval: 1000
        repeat: true
        onTriggered: {
            if (countdown >= 0) {
                countdown--;
                if (countdown == -1) {
                    X1PlusNative.system("/opt/kexec/boot");
                }
            }
        }
    }

    id: textConfirm
    width: 800
    height: textContent.contentHeight + 12 + subtitle.contentHeight
    
    Image {
        id: bambuman
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 128
        height: 128
        source: "../../image/cfw.png"
    }

    Text {
        id: textContent
        anchors.left: bambuman.right
        anchors.top: parent.top
        anchors.leftMargin: 24
        anchors.right: parent.right
        font: Fonts.body_36
        color: Colors.gray_100
        wrapMode: Text.Wrap
        text: hasSdCard ? qsTr("Bootable SD card detected.")
                        : qsTr("No bootable SD card detected.")
    }
    
    Text {
        id: subtitle
        anchors.top: textContent.bottom
        anchors.topMargin: 12
        anchors.left: textContent.left
        anchors.right: textContent.right
        width: textContent.width
        font: Fonts.body_32
        color: Colors.gray_200
        wrapMode: Text.Wrap
        text: hasSdCard 
            ? (countdown > 0) 
                ? qsTr("Your printer will automatically boot from the SD card in %1 seconds.").arg(countdown)
                : qsTr("Your printer is rebooting into the OS on the inserted SD card.")
            : qsTr("Insert a bootable SD card and restart the printer, or use the startup options menu to repair your X1Plus installation.")
    }
}
