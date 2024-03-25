import QtQuick 2.12
import UIBase 1.0
import QtQuick.Shapes 1.12
import DdsListener 1.0
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import Printer 1.0
import X1PlusNative 1.0

import "qrc:/uibase/qml/widgets"
import ".."
import '../X1Plus.js' as X1Plus

Item {
    id: vibcomp
    property string tab: "&nbsp;&nbsp;&nbsp;&nbsp;"
    property var task: PrintManager.currentTask
    property var sweepArgs: loadSweepArgs()
    property var _cal: X1Plus.ShaperCalibration

    function loadSweepArgs() {
        var a = DeviceManager.getSetting("cfw_vc",null);
        if (!(a instanceof Object) || !a.low || !a.high) {
            a = { "low": "10", "high": "220"};
        }
        return a;
    }

    Item {
        id: vibcompProgress

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
                    var latest = _cal.getEntry(_cal.lastCalibrationTime());
                    
                    pageStack.push("VibrationCompPlotter.qml");
                    pageStack.currentPage.calibrationData = latest;
                    _cal.idle();
                });
            }
        }
        
        onDialogShouldBeOpenChanged: {
            if (dialogShouldBeOpen && !dialogIsOpen) {
                dialogStack.popupDialog("WorkProgress", {
                    name: qsTr("Vibration Compensation"),
                    message: Qt.binding(function() {
                        if (_cal.status() == _cal.STATUS.STARTING) {
                            return  qsTr("Beginning vibration compensation calibration.");
                        } else if (_cal.status() == _cal.STATUS.SWEEPING) {
                            var progress = (_cal.lastFrequency() - _cal.currentRangeLow()) / (_cal.currentRangeHigh() - _cal.currentRangeLow() + 1) * 0.5;
                            if (_cal.currentAxis() == "x")
                                progress += 0.5;
                            var ax = _cal.currentAxis();
                            var axisStr = ax == "x" ? qsTr("X axis") : qsTr("Y axis");
                            progress = Math.round(progress * 100);
                            var f = _cal.lastFrequency();
                            var a = _cal.shaperData().axes[ax].points[f].a;
                            return qsTr("Sweeping %1\n%2 Hz: %3 dB\nProgress: %4%").arg(axisStr).arg(f).arg(a.toFixed(1)).arg(progress);
                        } else if (_cal.status() == _cal.STATUS.TIMED_OUT) {
                            return qsTr("An error has occurred and data collection timed out.");
                        }
                        console.log(`[x1p] VibrationComp: vibcompProgress contents are odd, ${_cal.status()}`);
                        return qsTr("Vibration compensation calibration: internal state error, status = %1").arg(_cal.status());
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
        width: 382
        height: 480
        anchors.left: parent.left
        anchors.top:  parent.top
        leftMargin: 26
        topMargin: 26
        id: descrPanel
        property string instructionsText: qsTr("The printer's built in vibration compensation calibration is used to mitigate ringing artifacts. This tool allows you to run customized calibration sweeps, and visualize the data for diagnostics; it captures both the raw frequency data and the final compensation parameters computed and used by the printer.<br><br>" +
                "All printers have a different frequency response curve. Changes over time in this response curve can often be caused by motor vibrations, changes in belt tension, toolhead binding, or other factors. Analyzing these frequency response data can guide you in diagnosing printer problems, and in identifying when the printer needs maintenance.<br><br>" +
                "Run a sweep from this page to begin.")

        Text {
            id: guidelabel1
            anchors.top: parent.top
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            font: Fonts.head_36
            color: Colors.brand
            text: qsTr("Vibration")
        }

        
        ZLineSplitter {
            id: stepSplit1
            alignment: Qt.AlignTop
            anchors.top: guidelabel1.bottom
            anchors.topMargin: 20
            padding: 15
            color: Colors.brand
        }

        Item {
            id: instrItem
            anchors.top: stepSplit1.bottom
            anchors.topMargin: 20
            anchors.left:parent.left
            anchors.leftMargin: 20
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            ListView {
                ScrollBar.vertical: ScrollBar {
                    interactive: true
                    policy: ScrollBar.AlwaysOn
                }
                interactive: true
                anchors.fill: parent
                model: [0]
                clip: true
                delegate: Item {
                    height: inst.implicitHeight
                    Text {
                        id: inst
                        width: instrItem.width - 10
                        text: descrPanel.instructionsText
                        wrapMode: Text.WordWrap
                        font: Fonts.body_24
                        color: "#AEAEAE"
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
            id: runbtn
            anchors.top:parent.top
            anchors.left:parent.left
            anchors.right:parent.right
            height:(parent.height/2)-5
            checked: true
            enabled: task.stage < PrintTask.WORKING && !_cal.isActive()
            text: qsTr("Run frequency sweep")
            onClicked: {
                _cal.start(parseInt(sweepArgs.low), parseInt(sweepArgs.high));
                console.log("[x1p] Starting vibration comp");
            }
        }

        Text {
            id: rangeLbl
            anchors.verticalCenter: rangeInput1.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin:12
            font: Fonts.head_24
            color: Colors.gray_100
            text: qsTr("Range:")
        }
        
        Choise {
            id: rangeInput1
            width: 95
            anchors.bottom: parent.bottom
            anchors.bottomMargin:15
            anchors.left:rangeLbl.right
            anchors.leftMargin:10
            textFont: Fonts.body_18
            listTextFont: Fonts.body_18
            model: ["10", "20","30", "40", "50", "60"]
            placeHolder: sweepArgs.low
            currentIndex: model.indexOf(sweepArgs.low)
            onCurrentTextChanged: {
                if (currentText != ""){
                    sweepArgs.low = currentText;
                    DeviceManager.putSetting("cfw_vc",sweepArgs);
                }
                    
            }
            
        }
        Text {
            id: rangeLbl2
            anchors.verticalCenter: rangeInput1.verticalCenter
            anchors.left:rangeInput1.right
            anchors.leftMargin:10
            font: Fonts.body_24
            color: Colors.gray_100
            text: qsTr("to")
        }
        Choise {
            id: rangeInput2
            width: rangeInput1.width
            anchors.verticalCenter: rangeInput1.verticalCenter
            anchors.left:rangeLbl2.right
            anchors.leftMargin:10
            textFont: Fonts.body_18
            listTextFont: Fonts.body_18
            model: ["200", "210","220", "230", "240", "250"]
            placeHolder: sweepArgs.high
            currentIndex: model.indexOf(sweepArgs.high)
            onCurrentTextChanged: {
                if (currentText != "") {
                    sweepArgs.high = currentText;
                    DeviceManager.putSetting("cfw_vc",sweepArgs);
                }
            }
        }
        Text {
            id: rangeLbl3
            anchors.verticalCenter: rangeInput1.verticalCenter
            anchors.left:rangeInput2.right
            anchors.leftMargin:5
            font: Fonts.body_24
            color: Colors.gray_100
            text: qsTr("Hz")
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
                            name: qsTr("Clear calibration logs"),
                            type: TextConfirm.YES_NO,
                            defaultButton: 0,
                            text: qsTr("This will remove all of your saved vibration compensation data.  Are you sure you want to proceed?"),
                            onYes: function() {
                                _cal.deleteAll();
                            },
                        })
            }
        }
            ZLineSplitter {
                id: stepSplit
                alignment: Qt.AlignTop
                anchors.top: guidelabel.bottom
                anchors.topMargin: 20
                padding: 15
                color: Colors.brand
            }
            Item {
                id: stepItem
                anchors.top: stepSplit.bottom
                anchors.topMargin: 3//10
                anchors.left:parent.left
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 10
                ListModel{
                    id:vibCompModel
                }
                ListView {
                    id: calData
                    anchors.fill: parent
                    anchors.leftMargin: 20
                    anchors.bottomMargin:10
                    interactive: true
                    spacing: 5
                    model: _cal.calibrationRuns().slice().reverse()
                    clip: true
                    delegate:
                    
                    Item {
                        property var run: _cal.getEntry(modelData)
                        property var runDate: X1Plus.formatTime(run.time)
                        property var runParams: `${run.low}-${run.high} Hz`
                        property var cfParams_wnX:  `${run.axes.x.summaries[0].wn .toFixed(0)}, ${run.axes.x.summaries[1].wn .toFixed(0)}`
                        property var cfParams_wnY:  `${run.axes.y.summaries[0].wn .toFixed(0)}, ${run.axes.y.summaries[1].wn .toFixed(0)}`
                        property var cfParams_ksiX: `${run.axes.x.summaries[0].ksi.toFixed(2)}, ${run.axes.x.summaries[1].ksi.toFixed(2)}`
                        property var cfParams_ksiY: `${run.axes.y.summaries[0].ksi.toFixed(2)}, ${run.axes.y.summaries[1].ksi.toFixed(2)}`
                        property var cfParams_pkX:  `${run.axes.x.summaries[0].pk .toFixed(0)}, ${run.axes.x.summaries[1].pk .toFixed(0)}`
                        property var cfParams_pkY:  `${run.axes.y.summaries[0].pk .toFixed(0)}, ${run.axes.y.summaries[1].pk .toFixed(0)}`

                        height: diagRes.implicitHeight + 15
                        width:parent.width
                        ZLineSplitter {
                            alignment: Qt.AlignTop
                            padding: 23
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
                                text: qsTr("<br>Run date: %1 %2 %3 <font size=\"3\" color=\"#AEAEAE\">" +
                                    "<br>X-axis: ω_n=%4 Hz %5 ksi=%6 %7 pk=%8 Hz" +
                                    "<br>Y-axis: ω_n=%9 Hz %10 ksi=%11 %12 pk=%13 Hz</font>")
                                    .arg(runDate).arg(tab).arg(runParams)
                                    .arg(cfParams_wnX).arg(tab).arg(cfParams_ksiX).arg(tab).arg(cfParams_pkX)
                                    .arg(cfParams_wnY).arg(tab).arg(cfParams_ksiY).arg(tab).arg(cfParams_pkY)
                                }
                        }
                        TapHandler {
                            onTapped: {     
                                console.log("[x1p] vibration: plotting data from",runDate);         
                                pageStack.push("VibrationCompPlotter.qml");
                                pageStack.currentPage.calibrationData = run;
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