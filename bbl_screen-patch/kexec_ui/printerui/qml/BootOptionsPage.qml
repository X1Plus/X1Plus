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
    
    function confirmThenDo(prompt, what, confirm) {
        dialogStack.popupDialog("TextConfirm", {
            name: "installer yesno",
            text: prompt,
            titles: [confirm, "Cancel"],
            onYes: function() { what(); },
            onNo: function() { dialogStack.pop(); }
        });
    }
    
    function startFromSd() {
        X1PlusNative.system("/opt/kexec/boot");
    }
    
    function startInstaller() {
        dialogStack.replace("SelectX1pPage.qml");
    }
    
    function promptWipeWritable() {
        confirmThenDo("Resetting X1Plus settings can help to recover from modified X1Plus installations.  " +
                      "It will also reset the lock screen passcode, root password, and ssh keys.  (This process takes a few minutes.)", 
                      function () {
                          /* load printer.json, and wipe any cfw keys */
                          let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/config/screen/printer.json";
                          let xhr = new XMLHttpRequest();
                          xhr.open("GET", path, /* async = */ false);
                          xhr.send();
                          let j = JSON.parse(xhr.response);
                          for (let k in j) {
                              if (k.startsWith('cfw_')) {
                                  console.log(`removing key ${k}`);
                                  delete j[k];
                              }
                          }
                          
                          X1PlusNative.saveFile(X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/config/screen/printer.json", JSON.stringify(j, null, 4));
                          
                          let ext4_path = X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/rw.ext4";
                          X1PlusNative.system(`rm -f ${ext4_path} && truncate -s ${1024*1024*1024} ${ext4_path} && mkfs.ext4 -F ${ext4_path}`);
                          let hostkey_path = X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/config/sshd/*";
                          X1PlusNative.system(`rm -f ${hostkey_path}`);
                          let sdcard_logs_path = X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/printers/${DeviceManager.build.seriaNO}/logs/*";
                          X1PlusNative.system(`rm -f ${sdcard_logs_path}`);
                          X1PlusNative.system(`sync`);
                          
                          dialogStack.pop();
                      }, "Wipe writable partition");
    }

    function promptEmergencyConsole() {
        confirmThenDo(
            "The emergency recovery console will connect the printer to its default WiFi network and start a temporary SSH server as root.  " +
            "It will also spawn a root console on the AP board's UART port and USB port." +
            "<br><br>It is possible to unrecoverably and permanently damage your printer with a root console.  Never type something into a root console unless you understand what you're typing.",
            function() {
                dialogStack.pop();
                dialogStack.replace("EmergencyConsole.qml");
            }, "I'll be careful, I promise");
    }

    
    function promptBootDisable() {
        confirmThenDo(
            "Starting from the built-in firmware can be useful to diagnose issues " +
            "with X1Plus or with your printer.  This option " +
            "attempts to enter LAN mode before starting, and disables the printer's internal upgrade " +
            "service; you can use this option to help avoid inadvertent erasure of your X1Plus installation." +
            "<br><br><font color=\"#EEAAAA\">Use this mode with caution.",
            function() {
                let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/config/device/conn_mode";
                let xhr = new XMLHttpRequest();
                xhr.open("PUT", path, /* async = */ false);
                xhr.send("lan"); /* This may not work, so we also set lan mode in disable_upgrade.sh */
                X1PlusNative.system("/opt/kexec/disable_upgrade.sh");
                Qt.quit();
            }, "Fingers are crossed");
    }
    
    function promptBootUnmodified() {
        confirmThenDo(
            "<font color=\"#EEAAAA\">Starting from the built-in firmware can be useful to diagnose issues " +
            "with X1Plus or with your printer.  This option starts the printer with no modifications to the " +
            "built-in firmware.  If your printer performs a firmware upgrade in this mode, X1Plus will likely " +
            "be uninstalled; if you want to run X1Plus afterwards, you will need to rerun the " +
            "X1Plus installation process.  If prompted to install upgrades, you should answer \"no\" if you want " +
            "to keep your X1Plus installation." +
            "<br><br>Use this mode with extreme caution.",
            function() {
                X1PlusNative.system("killall bbl_screen"); /* We need this else we hang for ages */
                Qt.quit();
            }, "Fingers are crossed");
    }
    
    /* Replicated in KexecDialog.qml; keep this in sync if you change this (or, really, refactor it then). */
    property var hasSdCard: (function () {
        let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/boot.conf";
        let xhr = new XMLHttpRequest();
        xhr.open("GET", path, /* async = */ false);
        xhr.send();
        return xhr.status == 200;
    }())
    property var startupOptions: ([
        ["Start X1Plus from SD card", hasSdCard, startFromSd],
        ["<b>Start X1Plus installer</b>", true, startInstaller],
        ["Reset X1Plus settings", true, promptWipeWritable],
        ["Emergency recovery console", true, promptEmergencyConsole],
        ["<font color=\"#EEAAAA\">Start built-in firmware with updater disabled</font>", true, promptBootDisable],
        ["<font color=\"#FF7777\">Start built-in firmware unmodified</font>", true, promptBootUnmodified]
    ])
    
    Text {
        id: titlelabel
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: 48
        anchors.leftMargin: 48
        anchors.right: parent.right
        font: Fonts.head_48
        color: Colors.brand
        text: "X1Plus startup options"
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
                text: "Use these tools to upgrade or repair the X1Plus firmware on your printer.<br><br><font color=\"#EEAAAA\"><b>Starting up using on-device firmware can result in your printer losing access to custom firmware.  Do this only as a last resort.</b></font>"
            }

            Image {
                id: icon
                anchors.horizontalCenter: descriptionText.horizontalCenter
                anchors.top: descriptionText.bottom
                anchors.topMargin: 48
                anchors.bottom: parent.bottom
                width: height
                source: "../image/cfw.png"
            }
        }
        
        Item {
            id: rframe
            anchors.left: lframe.right
            anchors.leftMargin: 36
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            
            Rectangle {
                radius: 16
                color: Colors.gray_600
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 0
                anchors.left: parent.left
                anchors.right: parent.right
                clip: true
                
                ListView {
                    anchors.top: parent.top
                    anchors.topMargin: 24
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 24
                    anchors.left: parent.left
                    anchors.right: parent.right
                    id: statusList
                    boundsBehavior: Flickable.StopAtBounds
                    model: startupOptions
                    delegate: statusComp
                }
            }
        }
    }
    
    Component {
        id: statusComp
        
        Rectangle {
            property var modelText: modelData[0]
            property var modelEnabled: modelData[1]
            property var modelAction: modelData[2]
            property var isLast: index == (ListView.view.model.length - 1)
            width: ListView.view.width
            height: 77
            radius: 10
            color: handler.active ? Colors.gray_500 : "transparent"
            
            ZLineSplitter {
                alignment: Qt.AlignTop
                padding: 55
                color: Colors.gray_400
                visible: index > 0
            }
            
            /*Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: "#ffffff"
            }*/
            
            Item {
                anchors.top: parent.top
                height: parent.height
                anchors.left: parent.left
                anchors.leftMargin: 24
                anchors.right: parent.right
                anchors.rightMargin: 18
                
                Image {
                    id: statusIcon
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    fillMode: Image.PreserveAspectFit
                    rotation: 90
                    source: "../image/up.svg"
                }
                
                Text {
                    id: statusTitle
                    wrapMode: Text.WordWrap
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: statusIcon.left
                    anchors.left: parent.left
                    anchors.leftMargin: 0
                    color: modelEnabled ? Colors.gray_100 : Colors.gray_400
                    font: Fonts.body_30
                    text: modelText
                }
            }
            
            TapHandler {
                id: handler
                enabled: modelEnabled
                gesturePolicy: TapHandler.ReleaseWithinBounds | TapHandler.WithinBounds
                onTapped: { startupOptions[index][2]() }
            }
        }
    }
}
