import QtQuick 2.12
import UIBase 1.0
import DdsListener 1.0
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import Printer 1.0
import X1PlusNative 1.0

import "qrc:/uibase/qml/widgets"
import ".."
import "../X1Plus.js" as X1Plus


Item {
    id: bedmeshcomp
    property var task: PrintManager.currentTask
    property var _cal: X1Plus.BedMeshCalibration

    Item {
        id: bedmeshProgress
        property var isTimedOut: _cal.status() == _cal.STATUS.TIMED_OUT
        property var isDone: _cal.status() == _cal.STATUS.DONE
        property var dialogShouldBeOpen: _cal.isActive() || isTimedOut
        property var dialogIsOpen: false
        
        Timer {
            id: timeoutMessageTimer
            interval: 5000
            onTriggered: {
                _cal.idle();
            }
        }
        
        onIsTimedOutChanged: {
            if (isTimedOut) {
                timeoutMessageTimer.start();
            }
        }
        
        onIsDoneChanged: {
            if (isDone) {
                Qt.callLater(function() {
                    runbtn.text = qsTr("Rerun diagnostics");

                    var latest = _cal.getEntry(_cal.lastCalibrationTime());
                    var metrics = latest.bedMetrics;
                    diagRes2.text = qsTr("<font size=\"3\" color=\"#AEAEAE\">%1<br><br>Calculated bed tilt (X-axis) is %2 mm across the X axis, and %3 mm across the Y axis; post-tramming peak-to-peak deviation is %4 mm.</font>")
                        .arg(X1Plus.MeshCalcs.describeMetrics(metrics))
                        .arg(metrics.tiltX.toFixed(2))
                        .arg(metrics.tiltY.toFixed(2))
                        .arg(metrics.nonplanarity.toFixed(2));
                    
                    pageStack.push("BedLevelDiag.qml");
                    pageStack.currentPage.calibrationData = latest;
                    _cal.idle();
                });
            }
        }
        
        onDialogShouldBeOpenChanged: {
            if (dialogShouldBeOpen && !dialogIsOpen) {
                dialogStack.popupDialog("WorkProgress", {
                    name: "Bed Mesh",
                    message: Qt.binding(function() {
                        if (_cal.status() == _cal.STATUS.STARTING) {
                            return "Bed mesh calibration: Toolhead is homing";
                        } else if (_cal.status() == _cal.STATUS.PROBING) {
                            var t = Math.round(_cal.pointCount() / _cal.N_MESH_POINTS * 100);
                            return `Probed point ${_cal.pointCount()}<br>X=${_cal.lastX()}, Y=${_cal.lastY()}&nbsp;&nbsp;Z=${_cal.lastZ()} mm\nProgress: ${t}%`
                        } else if (_cal.status() == _cal.STATUS.TIMED_OUT) {
                            return "An error has occurred and data collection timed out."
                        }
                        console.log(`[x1p] BedMesh: bedProgDialog contents are odd, ${_cal.status()}`);
                        return `Bed mesh calibration: internal state error, status = ${_cal.status()}`;
                    }),
                    finished: Qt.binding(function() {
                        return !dialogShouldBeOpen;
                    })
                });
            }
            dialogIsOpen = dialogShouldBeOpen;
        }
    }
    
    MarginPanel {
        id: descrPanel
        width: 382
        height: 440
        anchors.left: parent.left
        anchors.top:  parent.top
        leftMargin: 26
        topMargin: 26
        

        
        Text {
            id: guidelabel5
            anchors.top: parent.top
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            font: Fonts.head_36
            color: Colors.brand
            text: qsTr("Bed Diagnostics")
        }
        ZLineSplitter {
            id: stepSplit2
            anchors.top: guidelabel5.bottom
            anchors.topMargin: 10
            alignment: Qt.AlignTop
            padding: 15
            color: Colors.brand
        }
        Item {
            id: stepItem2
            anchors.top: stepSplit2.bottom
            anchors.topMargin: 20
            anchors.left:parent.left
            anchors.leftMargin:20
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10

            Text{
                id:diagRes2
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: diagRes2.implicitHeight+10
                wrapMode:Text.WordWrap
                color: Colors.gray_100
                font: Fonts.body_24
                text:"<font size=\"3\" color=\"#AEAEAE\">" + qsTr("If your prints are not flat and square, you may need to check whether your hotbed is level.<br><br>The printer's built-in automatic bed leveling can provide information as to whether your hotbed is out of level, or if it is warped.<br><br>Run the diagnostics to begin.")+"</font>"
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
            id: runbtn
            anchors.top:parent.top
            anchors.left:parent.left
            anchors.right:parent.right
            height:(parent.height/2)-5
            checked: true
            text: qsTr("Run diagnostics")
            enabled: task.stage < PrintTask.WORKING && !_cal.isActive()
            onClicked: {
                _cal.start();
            }
        }

        ZButton {
            id: trambtn
            anchors.left:parent.left
            anchors.right:parent.right
            anchors.bottom:parent.bottom
            height:runbtn.height
            width:runbtn.width
            checked: true
            text: qsTr("Tram bed")
            enabled: task.stage < PrintTask.WORKING && !_cal.isActive()
            onClicked: {
                pageStack.push("BedTramming.qml")
            }
        }
    }
  
    MarginPanel {
        id: caliPanel
        anchors.left: buttonPanel.right
        anchors.right:parent.right
        anchors.top:  parent.top
        anchors.bottom: parent.bottom
        leftMargin: 14
        topMargin: 26
        bottomMargin: 26
        rightMargin: 26

        Text {
            id: guidelabel
            anchors.top: parent.top
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            font: Fonts.head_36
            color: Colors.brand
            text: qsTr("Calibration History")
        }
        ZButton { 
            id: historyBtn
            icon: "../../icon/components/trash.svg"
            iconSize: 50
            width: 50
            type: ZButtonAppearance.Secondary
            anchors.right:parent.right
            anchors.rightMargin:10
            anchors.top:caliPanel.top
            anchors.topMargin: 5
            cornerRadius:width/2
            enabled:task.stage < PrintTask.WORKING && !_cal.isActive()
            onClicked: {
                dialogStack.popupDialog(
                        "TextConfirm", {
                            name: "clear calibration logs",
                            type: TextConfirm.YES_NO,
                            defaultButton: 0,
                            text: qsTr("This will clear all of your saved bed mesh data. Are you sure you want to proceed?"),
                            onYes: function() {
                                _cal.deleteAll();
                            }
                        });
            }
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
            anchors.topMargin: 3
            anchors.left:parent.left
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10

            ListView {
                id: calData
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.bottomMargin:10
                interactive: true
                spacing: 5
                model: _cal.calibrationRuns().slice().reverse()
                clip: true
                delegate: Item {
                    property var run: _cal.getEntry(modelData)
                    property var runDate: X1Plus.formatTime(run.time)
                    property var bedTemperature: `${run.temperature.toFixed(0)}°C`
                    property var xTilt: `${run.bedMetrics.tiltX.toFixed(2).toString()} mm`
                    property var yTilt: `${run.bedMetrics.tiltY.toFixed(2).toString()} mm`
                    property var peak: `${run.bedMetrics.peakToPeak.toFixed(2).toString()} mm`
                    
                    height: diagRes.implicitHeight + 15
                    width:parent.width
                    ZLineSplitter {
                        alignment: Qt.AlignTop
                        color: "#606060"
                        visible: index > 0
                    }
                    Image {
                        id: menuImage
                        width: height
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right
                        fillMode: Image.Pad
                        horizontalAlignment: Qt.AlignRight
                        source: "../../icon/right.svg"
                    }
                    Column {
                        width:parent.width
                        Text {
                            id: diagRes
                            width: stepItem.width
                            font: Fonts.body_24
                            color: Colors.gray_100
                            wrapMode: Text.WordWrap
                            text: qsTr("<br>Run date: %1&nbsp;&nbsp;&nbsp;&nbsp;Bed Temperature: %2 <font size='3' color='#AEAEAE'><br>X-tilt: %3<br>Y-tilt: %4<br>Peak to peak deviation: %5</font>")
                                .arg(runDate)
                                .arg(bedTemperature)
                                .arg(xTilt)
                                .arg(yTilt)
                                .arg(peak)
                        }
                        TapHandler {
                            onTapped: {                   
                                pageStack.push("BedLevelDiag.qml");
                                pageStack.currentPage.calibrationData = run;
                            }
                        }

                    }
                    
                }
                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }
            }

        }
    }

    Item{
        X1PBackButton {
            onClicked: { 
                pageStack.pop();
            }
        }
    }
}