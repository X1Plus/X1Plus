import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0

import "qrc:/uibase/qml/widgets"
import ".."
import "../printer"

Item {
    id: top
    property var passcode: DeviceManager.getSetting("cfw_passcode", "")
    Binding on passcode {
        value: numberPad.number
        when: numberPad.target == top
    }

    MarginPanel {
        id: title
        height: 68 + 39 + 20 + line.height + 20
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        radius: 0
        color: "#393938"

        Item {
            id: titlePanel
            height: 68
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 39

            Image {
                id: brandImage
                x: 28
                width: 57
                height: 68
                source: "../../icon/lockScreen.png"
            }

            Text {
                id: titleName
                anchors.left: brandImage.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                color: Colors.gray_200
                font: Fonts.body_36
                text: "Screen lock settings"
            }

            ZButton {
                id: returnBtn
                anchors.right: parent.right
                anchors.rightMargin: 28
                anchors.top: parent.top
                anchors.topMargin: 6
                checked: false
                text: qsTr("Return")
                onClicked: { parent.parent.parent.parent.pop() }
            }

            Rectangle {
                id: line
                height: 1
                anchors.left: brandImage.left
                anchors.right: parent.right
                anchors.rightMargin: 64
                anchors.top: brandImage.bottom
                anchors.topMargin: 20
                color: Colors.gray_500
            }
        }
    }

    MarginPanel {
        id: ctrlPanel
        width: 400
        anchors.top: title.bottom
        anchors.left: parent.left
        leftMargin: 16
        anchors.bottom: parent.bottom
        bottomMargin: 16
        radius: 15
        color: Colors.gray_600

        Text{
            id:diagRes2
            wrapMode:Text.WordWrap
            color: Colors.gray_100
            font: Fonts.body_28
            height: diagRes2.implicitHeight+10
            anchors.top: parent.top
            anchors.topMargin: 20
            anchors.left:parent.left
            anchors.leftMargin: 20
            anchors.right: parent.right
            anchors.rightMargin: 20
            
            text: qsTr("The screen lock is a low-security deterrence against casual passers-by, but it will not provide a strong defense against sophisticated attackers.<br><br>If the printer is connected to a network, you will still be able to print over the network when the screen is locked.")
        }
    }

    Rectangle {
        id: focus
        visible:false
    }
    property var sleepMapping: [ qsTr("2 minutes"), qsTr("5 minutes"), qsTr("10 minutes"), qsTr("15 minutes") ]
    
    MarginPanel {
        id: infosPanel
        anchors.left: ctrlPanel.right
        anchors.right: parent.right
        rightMargin: 16
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        bottomMargin: 15
        leftMargin: 16
        radius: 15
        color: Colors.gray_600

        Text {
            anchors.verticalCenter: choiceSleepTime.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 25
            id: lblSleepTime
            font: Fonts.body_30
            color: Colors.gray_100
            text: qsTr("Time before display sleeps")
        }
        
        Choise {
            id: choiceSleepTime
            anchors.right: parent.right
            anchors.rightMargin: 25
            anchors.top: parent.top
            anchors.topMargin: 25
            textFont: Fonts.body_26
            listTextFont: Fonts.body_28
            backgroundColor: Colors.gray_500
            model: sleepMapping
            currentIndex: DeviceManager.power.mode
            onCurrentIndexChanged: { DeviceManager.power.mode = currentIndex; }
        }

        Rectangle {
            id: line0
            height: 1
            anchors.left: parent.left
            anchors.leftMargin: 32
            anchors.right: parent.right
            anchors.rightMargin: 32
            anchors.top: choiceSleepTime.bottom
            anchors.topMargin: 15
            color: Colors.gray_300
        }
        
        Text {
            anchors.verticalCenter: choiceMode.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 25
            id: lblMode
            font: Fonts.body_30
            color: Colors.gray_100
            text: qsTr("Lock screen mode")
        }
        
        Choise {
            id: choiceMode
            anchors.right: parent.right
            anchors.rightMargin: 25
            anchors.top: line0.top
            anchors.topMargin: 15
            textFont: Fonts.body_26
            listTextFont: Fonts.body_28
            backgroundColor: Colors.gray_500
            width: 300
            model: [qsTr("Screen saver only"), qsTr("Swipe to unlock"), qsTr("Passcode")]
            currentIndex: DeviceManager.getSetting("cfw_locktype", 0)
            onCurrentIndexChanged: {
                DeviceManager.putSetting("cfw_locktype", currentIndex);
                const c = DeviceManager.power.mode; /* sort of janky mechanism to trigger the binding on the parent screen to reload */
                DeviceManager.power.mode = 3 - c;
                DeviceManager.power.mode = c;
                screenLock.refreshSettings();
            }
        }
        
        Rectangle {
            id: line1
            height: 1
            anchors.left: parent.left
            anchors.leftMargin: 32
            anchors.right: parent.right
            anchors.rightMargin: 32
            anchors.top: choiceMode.bottom
            anchors.topMargin: 15
            color: Colors.gray_300
        }
        Rectangle {
            width: lblSetPasscode.implicitWidth+10
            height: lblSetPasscode.height
            anchors.left: lblSetPasscode.left
            anchors.top:lblSetPasscode.top
            color: "#2AB637"
            visible: numberPad.target==top
            id:lbl
            
        }
        Text {
            anchors.verticalCenter: btnSetPasscode.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 25
            id: lblSetPasscode
            font: Fonts.body_30
            color: passcode == "" && choiceMode.currentIndex == 2 && numberPad.target != top ? "#FF8080" : Colors.gray_100
            text: numberPad.target == top 
                ? qsTr('Passcode: "%1"').arg(passcode)
                : (passcode == "" 
                    ? qsTr("Passcode is unset") 
                    : qsTr('Passcode set to "%1"').arg(passcode))


        }
        
        ZButton {
            id: btnSetPasscode
            anchors.right: parent.right
            anchors.rightMargin: 25
            anchors.top: line1.top
            anchors.topMargin: 15
            textSize: 26
            text:qsTr("Change passcode")
            type: ZButtonAppearance.Tertiary
            onClicked: {
                numberPad.target = top;
            }
        }

        Rectangle {
            id: line2
            height: 1
            anchors.left: parent.left
            anchors.leftMargin: 32
            anchors.right: parent.right
            anchors.rightMargin: 32
            anchors.top: btnSetPasscode.bottom
            anchors.topMargin: 15
            color: Colors.gray_300
        }

        Text {
            font: Fonts.body_28
            color: Colors.gray_100
            anchors.top: line2.bottom
            anchors.topMargin: 20
            anchors.left: parent.left
            anchors.leftMargin: 25
            anchors.right: parent.right
            anchors.rightMargin: 25
            text: qsTr("You can add custom text or a background image to the lock screen by creating one or both of the following files on the SD card:<br><br><b>Text</b>: /x1plus/lockscreen.txt<br><b>Image</b>: /x1plus/lockscreen.png")
            wrapMode:Text.WordWrap
        }
        
        NumberPad {
            id: numberPad
            anchors.top: line2.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            focusItem: focus
            onFinished: {
                if (cancel) {
                    passcode = DeviceManager.getSetting("cfw_passcode", "")
                } else {
                    DeviceManager.putSetting("cfw_passcode", number);
                    screenLock.refreshSettings();
                }
            }
        }
    }
}
