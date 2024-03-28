import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import QtQml 2.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import "../X1Plus.js" as X1Plus
import "qrc:/uibase/qml/widgets"
import ".."

Rectangle {
    id: top
    width:1180
    height:720
    property var locked: false
    property var isEnteringPasscode: false
    property var passcode: DeviceManager.getSetting("cfw_passcode", "")
    property var locktype: DeviceManager.getSetting("cfw_locktype", 0)
    /* 0 = screensaver only, 1 = swipe to unlock, 2 = passcode */
    property var lockImagePath: X1PlusNative.getenv("EMULATION_WORKAROUNDS") + DeviceManager.getSetting("cfw_lockscreen_image", '/mnt/sdcard/x1plus/lockscreen.png')
    property var lockImage: X1Plus.fileExists(lockImagePath) ? lockImagePath : "qrc:/printerui/image/lockscreen.png"
    color: Colors.gray_800
    visible: locked && locktype != 0
    
    property var customText: null

    Binding on passcode { //possibly a redundant property
        value: numberPad.number
        when: numberPad.target == lockText
    }

    ZRoundedImage {
        id: lockimg
        width:1180
        height:720
        anchors.fill: parent 
        originSource: "file://" + lockImage
        visible: X1Plus.fileExists(lockImage)
    }

    function readText() {
        let path = "file://" + X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard/x1plus/lockscreen.txt";
        let xhr = new XMLHttpRequest();
        xhr.open("GET", path, /* async = */ false);
        xhr.send();
        if (xhr.status == 200) {
            customText = xhr.response.replace(/'\n'/g, '<br>');
        }
    }

    
    Component.onCompleted: {
        if ((DeviceManager.getSetting("cfw_locktype", 0) == 2) && (DeviceManager.getSetting("cfw_passcode", "") != "")) {
            /* lock on boot with a passcode */
            didSleep();
            locked = true;
        }
    }
    
    TapHandler {
        onTapped: { }
    }

    function didSleep() {
        if (DeviceManager.getSetting("cfw_locktype", 0) != 0) {
            locked = true;
            readText();
        }
    }
    
    function refreshSettings() {
        passcode = DeviceManager.getSetting("cfw_passcode", "");
        locktype = DeviceManager.getSetting("cfw_locktype", 0);
    }
    
    NumberPad {
        id: numberPad
        anchors.top: parent.top
        anchors.topMargin: lockText.y + lockText.height + 100
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 300
        anchors.rightMargin: 300
        anchors.bottomMargin: 100
        focusItem: lockText
        onFinished: {
            isEnteringPasscode = false;
            if (!cancel) {
                if (number == passcode) {
                    locked = false;
                }
            }
            ersatzDialogStack.pop();
        }
    }

     function popNumberPad() {
        isEnteringPasscode = true;
        numberPad.target = top;
        /* this is admittedly extremely silly, since the dialogStack is beneath us */
        ersatzDialogStack.push(dialogStack.currentItem);
    }

    ColumnLayout {
        id: columnLayout
        anchors.fill: parent
            
        Text {
            id: lockText
            Layout.preferredHeight: 150 // Adjust as needed
            Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
            Layout.topMargin: 100
            font: Fonts.head_44
            color: Colors.brand
            // horizontalAlignment: Text.AlignHCenter
            text: isEnteringPasscode ? (numberPad.number == "" ? "Enter passcode." : `Enter passcode: ${numberPad.number}`) : "This printer is locked."
            onXChanged: {
                /* this is *astonishingly* chaotic */
                if (isEnteringPasscode) {
                    ersatzDialogStack.currentItem.focusPosition = ersatzDialogStack.currentItem.mapFromItem(lockText, 0, 0);
                }
            }
        }
    
        Text {
            color: Colors.gray_100
            visible: customText != null
            text: customText ? customText : ""
            font: Fonts.body_28
            horizontalAlignment: Text.AlignHCenter
            Layout.leftMargin: 100
            Layout.rightMargin: 100
            Layout.fillWidth: true
        }
        
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            id: slideToUnlock
            height: 150
            width: 900
            radius: parent.height / 2
            color: Colors.gray_700
        
            Text {
                id: slideText
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                anchors.fill: parent
                color: Colors.gray_400
                text: "Pull to unlock."
                font: Fonts.body_24
            }

            Rectangle {
                x: 0
                y: 0
                height: parent.height
                width: thumb.x + parent.height
                radius: height / 2
                color: "#558855"
            }
            
            Rectangle {
                id: thumb
                x: 0
                y: 0
                width: parent.height
                height: parent.height
                radius: width / 2
                color: Colors.brand
                border.color: Colors.gray_400
                border.width: 3
                
                DragHandler {
                    xAxis.enabled: true
                    xAxis.minimum: 0
                    xAxis.maximum: slideToUnlock.width - thumb.width
                    yAxis.enabled: false

                    onActiveChanged: {
                        if (!active) {
                            if (thumb.x == xAxis.maximum) {
                                if (locktype == 1 || passcode == "") {
                                    locked = false;
                                } else {
                                    popNumberPad();
                                }
                            }
                            thumb.x = 0;
                        }
                        
                    }
                }
            }
            
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: "transparent"
                border.color: Colors.gray_400
                border.width: 5
            }
        }
    }
    
    StackView {
        id: ersatzDialogStack
        anchors.fill: parent
        initialItem: Item { objectName: "initialItem" }
        pushEnter: null
        pushExit: null
        popEnter: null
        popExit: null
    }
}
