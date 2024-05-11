import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import DdsListener 1.0
import "qrc:/uibase/qml/widgets"

Item {
    property alias name: textConfirm.objectName
    property var x1pName: ""
    property var stage1: ""
    /* Replicated in BootOptionsPage.qml; keep this in sync if you change this (or, really, refactor it then). */
    property var hasSdCard: (function () {
        let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/boot.conf";
        let xhr = new XMLHttpRequest();
        xhr.open("GET", path, /* async = */ false);
        xhr.send();
        return xhr.status == 200;
    }())
    property var countdown: 10
    property string startupMode: (function () {
        if (stage1 !== "") {
            console.log("stage1", x1pName,stage1);
            return "stage1";
        } else if (x1pName !== "") {
            console.log("ota", x1pName,stage1);
            return "ota";
        } else {
            console.log("default", x1pName,stage1);
            return "default";
        }
    }())
     
    property var startupStrings: {
        "default": { /* Normal Boot: 10 sec dialog then boot X1Plus */
            "buttons": {
                "yes_confirm": {"text": qsTr("Boot X1Plus"), "action": function() { X1PlusNative.system("/opt/kexec/boot"); }},
                "no": {"text": qsTr("Startup options..."), "action": function() { dialogStack.replace("../BootOptionsPage.qml", {hasSdCard: hasSdCard}) }},
                "cancel": {"text": "", "action": function() {}},  
            },
            "title": qsTr("Bootable SD card detected."),
            "subtitle": function() {
                return qsTr("Your printer will automatically boot from the SD card in %1 seconds.").arg(countdown)
            }
        },
        "ota": {
            "buttons": {/* auto install x1p Boot: 10 sec dialog then tell InstallingPage.qml to start installing x1p */
                "yes_confirm": {"text": qsTr("Install"), "action": function() { dialogStack.replace("../InstallingPage.qml", {x1pName: x1pName}) }},
                "no": {"text": qsTr("Startup options"), "action": function() { dialogStack.replace("../BootOptionsPage.qml", {hasSdCard: hasSdCard}) }},
                "cancel": {"text": qsTr("Boot X1Plus"), "action": function() { X1PlusNative.system("/opt/kexec/boot"); }}
            },
            "title": qsTr("Update ready to install!"),
            "subtitle": function() {
                return qsTr("Automatically installing %1 in %2 seconds. To cancel or skip installation, select 'Startup options' or 'Boot X1Plus'.").arg(x1pName).arg(countdown);
            }
        }
    }

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "yes_confirm"
            title: startupStrings[startupMode].buttons["yes_confirm"].text
            isDefault: defaultButton == 0
            onClicked: startupStrings[startupMode].buttons["yes_confirm"].action()
            visible: hasSdCard && countdown > 0
        }
        DialogButtonItem {
            name: "no"
            title: startupStrings[startupMode].buttons["no"].text
            isDefault: defaultButton == 1
            onClicked: startupStrings[startupMode].buttons["no"].action()
            visible: countdown > 0
        }
        DialogButtonItem {
            name: "cancel"
            title: startupStrings[startupMode].buttons["cancel"].text
            isDefault: defaultButton == 2
            onClicked: startupStrings[startupMode].buttons["cancel"].action()
            visible: hasSdCard && countdown > 0 && startupStrings[startupMode].buttons["cancel"].text.length > 0
        }
    }


    Component.onCompleted: {
        if (startupMode == "stage1") {
            dialogStack.replace("../SelectX1pPage.qml", {noBackButton: true});
        }
    }

    Timer {
        id: timer
        interval: 1000
        repeat: true
        running: hasSdCard && startupMode !== "stage1"
        onTriggered: {
            countdown--;
            if (countdown == -1) {
                startupStrings[startupMode].buttons["yes_confirm"].action();
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
        text: hasSdCard ? startupStrings[startupMode].title : qsTr("No SD Card detected.")
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
        text: hasSdCard ? startupStrings[startupMode].subtitle() : qsTr("Please insert an SD card to continue.")
    }
}
