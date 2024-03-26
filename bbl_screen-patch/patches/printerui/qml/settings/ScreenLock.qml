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
    property var screenlock: X1Plus.ScreenLock
    property var locked: screenlock.screenLocked()
    property var isEnteringPasscode: false
    property var passcode: DeviceManager.getSetting("cfw_passcode", "")
    property var locktype: DeviceManager.getSetting("cfw_locktype", 0)
    /* 0 = screensaver only, 1 = swipe to unlock, 2 = passcode */
    property var lockImage: X1PlusNative.getenv("EMULATION_WORKAROUNDS") + DeviceManager.getSetting("cfw_lockscreen_image", '/mnt/sdcard/x1plus/lockscreen.png')
    color: Colors.gray_800
    visible: locked && screenlock.lockType() != 0
    
    property var customText: null
    
    id: top
    ZRoundedImage {
            id: lockimg
            anchors.fill: top
            cornerRadius: parent.radius
            originSource: "file://" + lockImage
            visible: X1Plus.fileExists(lockImage)
    }
    

    //this can be moved to a JS file too
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
        refreshSettings();
    }
    
    TapHandler {
        onTapped: { }
    }
    
    
    function refreshSettings() {
        //temporary until we get these migrated
        screenlock._setPassCode(DeviceManager.getSetting("cfw_passcode", ""));
        screenlock._setLockType(DeviceManager.getSetting("cfw_locktype", 0));
        if (locked){
            readText();
        }
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
                screenlock.checkCode(number);
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
        anchors.fill: parent
            
        Text {
            id: lockText
            Layout.alignment: Qt.AlignHCenter
            font: Fonts.head_44
            color: Colors.brand
            horizontalAlignment: Text.AlignHCenter
            text: isEnteringPasscode ? (numberPad.number === "" ? qsTr("Enter passcode.") : qsTr("Enter passcode: ") + numberPad.number) : qsTr("This printer is locked.")
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
            height: 150
            width: 900
            radius: height / 2
            color: Colors.gray_700
                
            Text {
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: Colors.gray_400
                text: qsTr("Pull to unlock.")
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
                    xAxis.enabled: true
                    xAxis.minimum: 0
                    xAxis.maximum: parent.parent.width - parent.width
                    yAxis.enabled: false
                        
                    onActiveChanged: {
                        if (!active) {
                            if (parent.x == xAxis.maximum) {
                                if (screenlock.shouldSwipe()){
                                    screenlock._setScreenLocked(false);
                                } else {
                                    screenlock._setScreenLocked(true);
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
