import QtQuick 2.0
import UIBase 1.0
import Printer 1.0

import "qrc:/uibase/qml/widgets"
import ".."

Item {
    id: selfTestPage

    property var usageTexts: [
        [qsTr("Device self-test"), qsTr("The self-test program diagnoses your device through a series of inspection actions. It can help you find equipment faults and provide appropriate solutions.")],
//        [qsTr("Preparation before device self-test"), qsTr("Before running a device self-test, please make sure that filament is loaded and nozzle and bed temperature are set in the Feeding tab.")]
    ]

    property var task: PrintManager.currentTask

    MarginPanel {
        id: usagePanel
        width: 677
        height: parent.height
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        leftMargin: 26
        topMargin: 26
        bottomMargin: 26
        
        Text {
            id: guideLabel
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 20
            font: Fonts.head_36
            color: Colors.brand
            text: usageTexts[0][0]
        }

        ZLineSplitter {
            id: stepSplit2
            anchors.top: guideLabel.bottom
            anchors.topMargin: 10
            alignment: Qt.AlignTop
            padding: 15
            color: Colors.brand
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 20
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.top: stepSplit2.bottom
            anchors.topMargin: 30
            font: Fonts.body_30
            color: Colors.gray_300
            wrapMode: Text.WordWrap
            text: usageTexts[0][1]
        }
        
        /*
        Repeater {
            model: usageTexts

            Item {
                x: 36
                y: index < 1 ? 62 : 300

                Text {
                    font: Fonts.head_36
                    color: Colors.gray_100
                    text: modelData[0]
                }

                Text {
                    y: 53
                    width: 600
                    font: Fonts.body_30
                    color: Colors.gray_300
                    wrapMode: Text.WordWrap
                    text: modelData[1]
                }
            }
        }
        */
    }

    MarginPanel {
        id: stepPanel
        height: 585
        anchors.top: parent.top
        anchors.left: usagePanel.right
        anchors.right: parent.right
        leftMargin: 14
        topMargin: 26
        bottomMargin: 26
        rightMargin: 26

        Text {
            x: 23
            y: 29
            font: Fonts.head_28
            color: Colors.brand
            text: qsTr("Self-test Flow")
        }

        ZLineSplitter {
            id: stepSplit
            alignment: Qt.AlignTop
            offset: 80
            padding: 15
            color: Colors.brand
        }

        ZStepBar {
            id: stepBar
            width: stepSplit.width
            anchors.left: stepSplit.left
            anchors.top: stepSplit.bottom
            anchors.right: parent.right
            anchors.topMargin: 25
            barColor: Colors.brand
            stepOffset: 80
            finishIcon: "../../icon/step_ok.svg"
            step: task.prepareStep
            steps: task.prepareSteps
            visible: task.model.subtaskId + "" === "self-test"
        }
    }

    MarginPanel {
        anchors.left: usagePanel.right
        anchors.right: parent.right
        anchors.top: stepPanel.bottom
        anchors.bottom: parent.bottom
        bottomMargin: 26
        leftMargin: 14
        topMargin: 14
        rightMargin: 26

        ZButton {
            id: startButton
            anchors.fill: parent
            checked: true
            text: qsTr("Start Self-test")
            enabled: task.stage < PrintTask.WORKING
            onClicked: {
                // May pop up error dialog if filament not loaded
                PrintManager.selfTest()
            }
        }
    }

    X1PBackButton {
        onClicked: {
            pageStack.pop()
        }
    }
}
