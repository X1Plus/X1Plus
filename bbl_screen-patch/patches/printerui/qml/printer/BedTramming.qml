import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0
import DdsListener 1.0
import "qrc:/uibase/qml/widgets"
import ".."
import '../X1Plus.js' as X1Plus

Item {
    id: bedtramming
    property var task: PrintManager.currentTask
    property bool isTramming: false
    property bool emulating: X1Plus.emulating != ""
    property var buttonSelected: -1
    property bool isIdle: task.stage < PrintTask.WORKING && X1Plus.DDS.gcodeAction() != 254
    property var gcodeLibrary: X1Plus.GcodeGenerator
    
    property var stepList: [
        [qsTr("Step 1:"), qsTr("Set the bed screws to their baseline tension setting, as described in the \"Prepare for Bed Leveling\" section of the Bambu Lab wiki.  (A QR code link is given at the bottom of this text.)")],
        [qsTr("Step 2:"), qsTr("Tap the \"Prepare\" button below to home the bed.")],
        [qsTr("Step 3:"), qsTr("Tap the \"1\" button to move the nozzle to the front left position.  Adjust the front left bed adjustment screw until the nozzle just barely touches the bed.")],
        [qsTr("Step 4:"), qsTr("Adjust the front right and rear positions by tapping their corresponding button and adjusting their corresponding screws.")],
        [qsTr("Step 5:"), qsTr("Check each position in order, repeating all three until no further adjustment is needed.")],
        ["IS_QR_CODE", "https://wiki.bambulab.com/en/x1/manual/manual-bed-leveling"]
    ]

    Component.onCompleted: {
        canvas.requestPaint();
    }

    MarginPanel {
        id: descrPanel
        width: 382
        height: 470+67
        anchors.left: parent.left
        anchors.top:  parent.top
        leftMargin: 26
        topMargin: 26

        
        Text {
            id: guidelabel
            anchors.top: parent.top
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            font: Fonts.head_36
            color: Colors.brand
            text: qsTr("Bed Tramming")
        }


        ZLineSplitter {
            id: stepSplit
            alignment: Qt.AlignTop
            anchors.top: guidelabel.bottom
            anchors.topMargin: 10
            padding: 15
            color: Colors.brand
        }

        Item {
            id: stepItem
            anchors.top: stepSplit.bottom
            anchors.topMargin: 20
            anchors.left:parent.left
            anchors.leftMargin:20
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10

            ListView {
                ScrollBar.vertical: ScrollBar {
                    interactive: true
                    policy: ScrollBar.AlwaysOn
                }
                id: instructions
                anchors.fill: parent
                interactive: true
                spacing: 10
                model: stepList
                clip: true
                delegate: Item {
                    height: modelData[0] == "IS_QR_CODE" ? qrCode.size : stepTx.implicitHeight + 5
                    width: parent.width - 15
                    
                    QRCodeImage {
                        id: qrCode
                        size: parent.width
                        data: modelData[1]
                        visible: modelData[0] == "IS_QR_CODE"
                    }
                    
                    Text {
                        id: stepTx
                        width: parent.width
                        font: Fonts.body_24
                        color: Colors.gray_100
                        wrapMode: Text.WordWrap
                        text: modelData[0] + " <font size=\"3\" color=\"#AEAEAE\">" + modelData[1]+"</font>"
                        visible: modelData[0] != "IS_QR_CODE"
                    }
                }
            }
        }

    }

    MarginPanel {
        id: buttonPanel
        anchors.left: parent.left
        anchors.top: descrPanel.bottom
        anchors.bottom: parent.bottom
        anchors.right: descrPanel.right
        leftMargin: descrPanel.leftMargin
        topMargin: 14
        bottomMargin: 26

        ZButton {
            id: prepbtn
            anchors.fill: parent
            checked: true
            text: qsTr("Prepare")
            enabled: task.stage < PrintTask.WORKING && !isTramming
            onClicked: {
                isTramming = true;
                buttonSelected = -1;
                const trammingGcode = gcodeLibrary.Tramming.prepare();
                X1Plus.sendGcode(trammingGcode);
            }
        }
    }

    MarginPanel {
        id: caliPanel
        anchors.left: buttonPanel.right
        anchors.right:parent.right
        anchors.top:  parent.top
        anchors.bottom: parent.bottom
        topMargin:    descrPanel.topMargin
        bottomMargin: buttonPanel.bottomMargin
        leftMargin: 14
        rightMargin: 26

        Canvas {
    	id: canvas
        width:514
        height:554
        anchors.centerIn: parent

    	onPaint: {
            var XRES = canvas.width;
    	    var YRES = canvas.height;
    	    var XBED = 256;
    	    var YBED = 256;
    	    var BEDSCALE = 2.0;
    	    var BEDOFS = 40;
    	    
    	    var ctx = getContext("2d");

            ctx.save();
            ctx.translate(1, 21);
            ctx.scale(BEDSCALE, BEDSCALE);

            // draw a hotbed
            ctx.strokeStyle = 'rgba(192, 192, 192, 1.0)';
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(XBED / 3, 0);
            ctx.lineTo(XBED / 3 + 10, -10);
            ctx.lineTo(XBED * 2 / 3 - 10, -10);
            ctx.lineTo(XBED * 2 / 3, 0);
            ctx.lineTo(XBED, 0);
            ctx.lineTo(XBED, YBED);
            ctx.lineTo(XBED * 2 / 3, YBED);
            ctx.lineTo(XBED * 2 / 3 - 10, YBED + 10);
            ctx.lineTo(0, YBED + 10);
            ctx.lineTo(0, 0);
            ctx.stroke();
            ctx.restore();
    	    }
        }
        ZButton {
            id: rc
            height: 90
            anchors.topMargin: 20
            anchors.top:canvas.top
            anchors.horizontalCenter:canvas.horizontalCenter
            width: 120
            textSize:fl.textSize
            checked: true
            text: qsTr("Rear\n   2") // rear center
            enabled: isIdle && isTramming && buttonSelected != 1
            onClicked: {
                buttonSelected = 1;
                const trammingGcode = gcodeLibrary.Tramming.rear_center();
                X1Plus.sendGcode(trammingGcode);
            }
        }

        ZButton {
            id: fl
            height: rc.height
            anchors.horizontalCenter:canvas.horizontalCenter
            anchors.bottomMargin: 30
            anchors.bottom:canvas.bottom
            anchors.horizontalCenterOffset:-190
            width: rc.width
            checked: true
            text: qsTr("Front L\n     1") // front left
            enabled: isIdle && isTramming && buttonSelected != 2
            onClicked: {
                buttonSelected = 2;
                const trammingGcode = gcodeLibrary.Tramming.front_left();
                X1Plus.sendGcode(trammingGcode);
            }
        }
        ZButton {
            id: fr
            height: rc.height
            anchors.horizontalCenter:canvas.horizontalCenter
            anchors.bottomMargin: 30
            anchors.bottom:canvas.bottom
            anchors.horizontalCenterOffset:190
            width: fl.width
            checked: true
            text: qsTr("Front R\n     3") // front right
            enabled: isIdle && isTramming && buttonSelected != 3
            onClicked: {
                buttonSelected = 3;
                const trammingGcode = gcodeLibrary.Tramming.front_right();
                X1Plus.sendGcode(trammingGcode);
            }
        }
    }
    Item {
        X1PBackButton {
            onClicked: { 
                if (emulating == false && isTramming == true) {
                    const trammingGcode = gcodeLibrary.Tramming.exit();
                    X1Plus.sendGcode(trammingGcode);
                }
                isTramming = false;
                pageStack.pop();   
            }
        }
    }

}