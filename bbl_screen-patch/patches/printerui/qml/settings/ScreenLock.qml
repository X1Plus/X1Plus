import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import QtQml 2.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0

import "qrc:/uibase/qml/widgets"
import ".."

Rectangle {
    property var locked: false
    property var isEnteringPasscode: false
    property var passcode: DeviceManager.getSetting("cfw_passcode", "")
    property var locktype: DeviceManager.getSetting("cfw_locktype", 0)
    /* 0 = screensaver only, 1 = swipe to unlock, 2 = passcode */
    property var lockImage: X1PlusNative.getenv("EMULATION_WORKAROUNDS") + DeviceManager.getSetting("cfw_lockscreen_image", '/mnt/sdcard/x1plus/lockscreen.png')
    color: Colors.gray_800
    visible: locked && locktype != 0
    
    property var customText: null
    
    id: top
    ZRoundedImage {
            id: lockimg
            anchors.fill: top
            cornerRadius: parent.radius
            originSource: "file://" + lockImage
            visible: imgExists(lockImage)
    }
    function imgExists(img){
        if (X1PlusNative.popen(`test -f ${img} && echo 1 || echo 0`) == 0){
            return false;
        } else {
            return true;
        }
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
        gesturePolicy: TapHandler.ReleaseWithinBounds | TapHandler.WithinBounds
        onTapped: { }
    }
    
    function didSleep() {
        if (DeviceManager.getSetting("cfw_locktype", 0) != 0) {
            locked = true;
            readText();
            isEnteringPasscode = false;
            numberPad.target = null;
            dialogStack.clear(); // in case anything got left over somehow...
            dialogStack.push(dummyStackItem);
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
            target = null;
            if (!cancel) {
                if (number == passcode) {
                    locked = false;
                }
            }
        }
    }

    function popNumberPad() {
        if (!isEnteringPasscode) {
            isEnteringPasscode = true;
            numberPad.target = top;
        }
    }

    ColumnLayout {
        anchors.fill: parent
            
        Text {
            id: lockText
            Layout.alignment: Qt.AlignHCenter
            font: Fonts.head_44
            color: Colors.brand
            horizontalAlignment: Text.AlignHCenter
            text: isEnteringPasscode 
                ? (numberPad.number == "" 
                    ? qsTr("Enter passcode.") 
                    : qsTr("Enter passcode: %1").arg(numberPad.number)) 
                : qsTr("This printer is locked.")
            onXChanged: {
                /* this is *astonishingly* chaotic */
                if (isEnteringPasscode) {
                    dialogStack.currentItem.focusPosition = dialogStack.currentItem.mapFromItem(lockText, 0, 0);
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
            height: 150
            width: 900
            radius: height / 2
            color: Colors.gray_700
                
            Text {
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: Colors.gray_400
                text: "Pull to unlock."
                font: Fonts.body_24
                anchors.fill: parent
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
                height: parent.height
                width: parent.height
                radius: height / 2
                color: Colors.brand
                border.color: Colors.gray_400
                border.width: 3
                
                DragHandler {
                    xAxis.enabled: !isEnteringPasscode
                    xAxis.minimum: 0
                    xAxis.maximum: parent.parent.width - parent.width
                    yAxis.enabled: false
                        
                    onActiveChanged: {
                        if (!active) {
                            if (parent.x == xAxis.maximum) {
                                if (locktype == 1 || passcode == "") {
                                    locked = false;
                                } else {
                                    popNumberPad();
                                }
                            }
                            parent.x = 0;
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
    
    /* Shadow the global dialogStack here -- that dialogStack is hidden, but
     * the NumberPad uses it to push and pop things.  Ours isn't hidden. */
    StackView {
        id: dialogStack
        anchors.fill: parent
        initialItem: Item { objectName: "initialItem" }
        pushEnter: null
        pushExit: null
        popEnter: null
        popExit: null
    }
    
    // "StackView.pop()" apparently is a no-op not just when depth is 0, BUT
    // WHEN IT IS 1 ALSO.  So you cannot pop() down to the initialItem, you
    // can only clear() down to it.  Fucking QML!
    Component {
        id: dummyStackItem
        Item {
        }
    }
}
