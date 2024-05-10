import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import DdsListener 1.0
import "qrc:/uibase/qml/widgets"

Item {
    property alias name: textConfirm.objectName
    property var x1pName: ""

    /* Replicated in BootOptionsPage.qml; keep this in sync if you change this (or, really, refactor it then). */
    property var hasSdCard: (function () {
        let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/boot.conf";
        let xhr = new XMLHttpRequest();
        xhr.open("GET", path, /* async = */ false);
        xhr.send();
        return xhr.status == 200;
    }())
    property var countdown: 10
    property string startupMode: "default"

    property var startupStrings: {
        "default": { /* start mode default: no x1p update ready - display normal boot dialog */
            "buttons": {
                "yes_confirm": {"text": qsTr("Boot X1Plus"), "action": function() { X1PlusNative.system("/opt/kexec/boot"); }},
                "no": {"text": qsTr("Startup options..."), "action": function() { dialogStack.replace("../BootOptionsPage.qml", {hasSdCard: hasSdCard}) }},
                "cancel": {"text": "", "action": function() {}}, //do not display cancel button
            },
            "title": qsTr("Bootable SD card detected."),
            "subtitle": function() {
                return qsTr("Your printer will automatically boot from the SD card in %1 seconds.").arg(countdown)
            }
        },
        "updaterNotify": {/* start mode updaterNotify: .x1p update exists, give install option */
            "buttons": {
                "yes_confirm": {"text": qsTr("Boot X1Plus"), "action": function() { X1PlusNative.system("/opt/kexec/boot") }},
                "no": {"text": qsTr("Install"), "action":  function() { dialogStack.replace("../InstallingPage.qml", {x1pName: x1pName}) }},
                "cancel": {"text": qsTr("Startup options"), "action": function() { dialogStack.replace("../BootOptionsPage.qml", {hasSdCard: hasSdCard}) }},
            },
            "title": qsTr("Update ready to install!"),
            "subtitle": function() {
                return qsTr("An X1Plus update is ready! Press 'Install' if you wish to update to %1 now. Booting to SD in %2 seconds.").arg(x1pName).arg(countdown);
            },
        },
        "autoInstall": {/* start mode autoInstall: .x1p update exists and autoInstall=true */
            "buttons": {
                "yes_confirm": {"text": qsTr("Install"), "action": function() { dialogStack.replace("../InstallingPage.qml", {x1pName: x1pName}) }},
                "no": {"text": qsTr("Startup options"), "action": function() { dialogStack.replace("../BootOptionsPage.qml", {hasSdCard: hasSdCard}) }},
                "cancel": {"text": qsTr("Boot X1Plus"), "action": function() { X1PlusNative.system("/opt/kexec/boot"); }}
            },
            "title": qsTr("Installing X1Plus update."),
            "subtitle": function() {
                return qsTr("Automatically installing %1 in %2 seconds. To cancel or skip installation, select 'Startup options' or 'Boot X1Plus'.").arg(x1pName).arg(countdown);
            }
        },
       
    }
    function menuText(index, type) {
        var entry = startupStrings[index].buttons;
        return entry && entry[type] ? entry[type].text : "";
    }

    function menuAction(index, type) {
        var entry = startupStrings[index].buttons;
        if (entry && entry[type]) {
            entry[type].action();
        }
    }
    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "yes_confirm"
            title: menuText(startupMode, "yes_confirm")
            isDefault: defaultButton == 0
            onClicked: function() { menuAction(startupMode, "yes_confirm"); }
            visible: hasSdCard && countdown > 0
        }
        DialogButtonItem {
            name: "no"
            title: menuText(startupMode, "no")
            isDefault: defaultButton == 1
            onClicked: function() { menuAction(startupMode, "no"); }
            visible: countdown > 0
        }
        DialogButtonItem {
            name: "cancel"
            title: menuText(startupMode, "cancel")
            isDefault: defaultButton == 2
            onClicked: function() { menuAction(startupMode, "cancel"); }
            visible: hasSdCard && countdown > 0 && menuText(startupMode, "cancel").length > 0
        }
    }


    Component.onCompleted: {
        if (startupMode === "installerSelect") {
            dialogStack.replace("../SelectX1pPage.qml", {noBackButton: true});
        }
    }

    Timer {
        id: timer
        running: hasSdCard && startupMode !== "installerSelect"
        interval: 1000
        repeat: true
        onTriggered: {
            countdown--;
            if (countdown == -1) {
                if (startupMode == "installerSelect") { //install.sh, go directly to x1p selection menu
                    dialogStack.replace("../SelectX1pPage.qml", {noBackButton: true});
                }else { //default, updaterNotify, and autoInstall
                    menuAction(startupMode, "yes_confirm");
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
        text: hasSdCard ? startupStrings[startupMode].title : noHasSdCardStr.title
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
        text: hasSdCard ? startupStrings[startupMode].subtitle() : noHasSdCardStr.subtitle
    }
}
