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
    
    property var x1pName: null
    property var secondaryStatusText: null /* "<i>Blah</i>" */
    property var statusModel: [ ] /* [ ["success", "thing 1"], ["", "thing 2"], ["failure", "failed thing 3" ] ] */
    
    function gotDdsEvent(topic, dstr) {
        if (topic == "device/report/upgrade") {
            console.log("DDS event", topic, dstr);
            var datum = JSON.parse(dstr);
            if (datum.command == 'x1plus') {
                if (datum.progress) {
                    statusModel.push(["", datum.progress]);
                    secondaryStatusText = null;
                }
                if (datum.progress_interim) {
                    secondaryStatusText = datum.progress_interim;
                }
                if (datum.progress_success) {
                    statusModel[statusModel.length - 1][0] = "success";
                }
                if (datum.progress_failure) {
                    statusModel[statusModel.length - 1][0] = "failure";
                    secondaryStatusText = datum.progress_failure;
                    /* XXX: pop up a box */
                }
                if (datum.progress_complete) {
                    statusModel.push(["success", "Installation complete!"]);
                    dialogStack.popupDialog("Success", { });
                }
                var lastContentY = statusList.contentY;
                statusModel = statusModel; // force the ListView to update
                statusList.contentY = lastContentY;
                if (datum.progress || datum.progress_complete) {
                    statusList.positionViewAtEnd();
                }
                if (datum.prompt_yesno) {
                    dialogStack.popupDialog("TextConfirm", {
                        name: "installer yesno",
                        text: datum.prompt_yesno,
                        titles: ["Yes", "No"],
                        onYes: function() { DdsListener.publishJson("device/request/upgrade", JSON.stringify({ command: 'x1plus', yesno: true })); dialogStack.pop(); },
                        onNo: function() { DdsListener.publishJson("device/request/upgrade", JSON.stringify({ command: 'x1plus', yesno: false })); dialogStack.pop(); }
                    });
                }
            }
        }
    }
    
    Timer {
        /* This is super hokey, to allow a paint after we say 'unpacking
         * firmware bundle' but before we go to sleep for a while doing it. 
         */
        id: unpackTimer
        repeat: false
        interval: 250
        onTriggered: {
            // Only turn on WiFi if we are in the preboot environment, and
            // there are no cloud services running.
            let canStartWifi = X1PlusNative.popen("pidof device_manager") == "";
            
            let netcontents = X1PlusNative.readFile(X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/userdata/cfg/bbl_netservice_wlan0.conf").toString();
            if (netcontents != "") {
                netcontents = JSON.parse(netcontents);
                if (netcontents.net_switch == "OFF") {
                    canStartWifi = false;
                }
            }
            
            if (canStartWifi) {
                console.log("[x1p] turning on WiFi");
                // Do this as early as possible -- turn on the WiFi, so there's plenty of time for it to spool up.
             
                X1PlusNative.system('echo 1 > /sys/class/rfkill/rfkill1/state');
                X1PlusNative.system('wpa_supplicant_hook.sh &');
                X1PlusNative.system('while true ; do iwconfig wlan0 power off > /dev/null 2>&1 ; sleep 4 ; done &');
            }

            var rv = X1PlusNative.system(`mkdir -p /userdata/x1plus && cd /userdata/x1plus && unzip -p /sdcard/${x1pName} payload.tar.gz | gunzip | tar xv`);
            // We should probably error check this somehow -- do an XHR to make sure the launch script is there?
            statusModel[statusModel.length - 1][0] = "success";
            statusModel = statusModel;
            secondaryStatusText = "";
            X1PlusNative.system('mount -o remount,exec /userdata'); // Firmware R mounts it noeexec
            X1PlusNative.system(`/userdata/x1plus/install.sh &`); // this will soon start communicating with us over DDS, hopefully
        }
    }
    
    Component.onCompleted: {
        if (x1pName) {
            statusModel.push(["", "Unpacking installer"]);
            secondaryStatusText = `Extracting ${x1pName} to internal storage.`;
            statusModel = statusModel;
            /* Allow a paint before we start. */
            unpackTimer.start()
        }
        DdsListener.gotDdsEvent.connect(gotDdsEvent);
    }
    
    Component.onDestruction: {
        DdsListener.gotDdsEvent.disconnect(gotDdsEvent);
    }

    Text {
        id: titlelabel
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: 48
        anchors.leftMargin: 48
        anchors.right: parent.right
        font: Fonts.head_48
        color: Colors.brand
        text: "X1Plus custom firmware installation"
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
                text: "<b>Welcome to X1Plus!</b><br><br>The X1Plus custom firmware is being installed on your SD card.  This process could take up to 10 minutes.  Try to avoid powering your printer off."
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
                color: Colors.gray_800
                anchors.top: parent.top
                anchors.bottom: secondaryStatus.visible ? secondaryStatus.top : parent.bottom
                anchors.bottomMargin: secondaryStatus.visible ? 24 : 0
                anchors.left: parent.left
                anchors.right: parent.right
                clip: true
                
                ListView {
                    Component.onCompleted: positionViewAtEnd()
                    anchors.top: parent.top
                    anchors.topMargin: 24
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 24
                    anchors.left: parent.left
                    anchors.right: parent.right
                    id: statusList
                    boundsBehavior: Flickable.StopAtBounds
                    model: statusModel
                    delegate: statusComp
                }
            }
            
            Text {
                id: secondaryStatus
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                font: Fonts.body_28
                text: secondaryStatusText
                visible: secondaryStatusText != null
                color: Colors.gray_200
                wrapMode: Text.Wrap
            }
        }
    }
    
    Component {
        id: statusComp
        
        Item {
            property var isLast: index == (ListView.view.model.length - 1)
            width: ListView.view.width
            height: Math.max(60, statusTitle.implicitHeight)
            
            /*
            ZLineSplitter {
                alignment: Qt.AlignTop
                padding: 23
                color: "#ffffff"
                visible: index > 0
            }
            
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: "#ffffff"
            }
            */
            
            Item {
                anchors.top: parent.top
                height: parent.height
                anchors.left: parent.left
                anchors.leftMargin: 24
                anchors.right: parent.right
                anchors.rightMargin: 24
                
                Image {
                    id: statusIcon
                    anchors.verticalCenter: parent.verticalCenter
                    fillMode: Image.PreserveAspectFit
                    width: height
                    height: 48
                    source: modelData[0] == "success" ? "../image/roundHook.svg" : modelData[0] == "failure" ? "../image/exclamation.svg" : ""
                }
                
                Text {
                    id: statusTitle
                    wrapMode: Text.WordWrap
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: statusIcon.right
                    anchors.leftMargin: 18
                    width: parent.width - 48 - 18 // ???
                    color: isLast ? "#FFFFFF" : Colors.gray_200
                    font: isLast ? Fonts.head_30 : Fonts.body_30
                    text: modelData[1]
                }
            }
        }
    }
}
