import QtQuick 2.12
import QtQuick.Shapes 1.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import "../X1Plus.js" as X1Plus

import "qrc:/uibase/qml/widgets"
import ".."

// Speed Adjustment UI
// 

Rectangle {
    id: speedDial
    width: parent.width
    height: parent.height
    anchors.fill: parent
    color:"#B20D0F0D"
    property alias speed: dial.value
    property bool ramping: false
    property int mode: 0 
    property var targetSpeed:100
    property var currentSpeed: PrintManager.currentTask.printSpeed
    property var layerNum: PrintManager.currentTask.layerNum
    property var totalLayerNum: PrintManager.currentTask.totalLayerNum
    property var target: parent.target
    property var nearestLevel: function(val) { 
        var closestIndex = 0; 
        var minDiff = Math.abs(val - speedValues[0]);
        for (var i = 1; i < speedValues.length; i++) {
            var diff = Math.abs(val - speedValues[i]);
            if (diff < minDiff) {
                minDiff = diff; 
                closestIndex = i;
            }
        }
        return closestIndex; 
    }
    
    function updateDial() {
        dialCanvas.requestPaint();
    }

    onTargetChanged:{
        if (target != null){
            dialCanvas.requestPaint();
        }
    }
    Component.onCompleted: {
        updateDial();
        targetSpeed = currentSpeed;
    }
    
    /* Button for switching to stepbar */
    Rectangle {
        id: toStepbar
        width: 60
        height: 60
        color: Colors.gray_600
        x: 160
        y: 20
        z:1
        visible: customSpeed
        
        ZImage {
            id: defaultButton
            width: 60
            height: 60
            anchors.fill:parent
            fillMode: Image.PreserveAspectFit 
            originSource:  "../../icon/right.svg"
            transform: Scale {
                origin.x: defaultButton.width / 2
                origin.y: defaultButton.height / 2
                xScale: customSpeed ? -1 : 1
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                customSpeed = false;
                X1Plus.Settings.put("printerui.speedadjust", customSpeed);
                stepBar.step = nearestLevel(currentSpeed);
                PrintManager.currentTask.printSpeedMode = nearestLevel(currentSpeed);
            }
        }
    }

    Rectangle {
        id: dialRect
        width: 540
        height: 591
        anchors.centerIn: parent
        radius: 15
        color: Colors.gray_600
        MouseArea {
            anchors.fill: parent
            onPressed: mouse.accepted = true
        }
        Text {
            id: title
            text:qsTr("Print Speed")
            font.pixelSize: 36
            color: "white"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 40
        }
        Dial {
            id: dial
            width: 190*1.3
            height: 190*1.3
            from: 30
            stepSize:2
            to:180
            value: PrintManager.currentTask.printSpeed;
            anchors.centerIn: parent
            Component.onCompleted: {
                updateDial();
            }
            onValueChanged: {
                dial.value = Math.round(dial.value / dial.stepSize) * dial.stepSize;
                dial.value = 2 * Math.floor(dial.value / 2);
                targetSpeed = dial.value;
                updateDial();
            }
            background: Rectangle {
                id: dialBackground
                implicitWidth: 190*1.3
                implicitHeight: 190*1.3
                width:implicitWidth
                height:implicitHeight
                color: "#2F302F"
                radius: implicitWidth/2
                anchors.fill: parent

                Canvas {
                    id: dialCanvas
                    anchors.fill: parent
                    onPaint: {
                        var ctx = getContext("2d");
                        var centerX = width / 2;
                        var centerY = height / 2;
                        var radius = Math.min(centerX, centerY) - 5; //tick positioning
                        ctx.clearRect(0, 0, width, height);

                        var startAngle = 130;
                        var endAngle = 270;
                        var range = dial.to - dial.from;
                        
                        var stepAngle = (startAngle - endAngle) / range * dial.stepSize;
                        var currentAngle = startAngle - ((dial.value - dial.from) * stepAngle); // calculate angle for current value

                        // Draw arc for the current value
                        ctx.beginPath();
                        ctx.arc(centerX, centerY, radius - 10,  currentAngle * Math.PI / 180,startAngle * Math.PI / 180, true);
                        ctx.strokeStyle = "rgba(180, 180, 180, 0.25)";
                        ctx.lineWidth = 20;
                        ctx.stroke();

                        for (var i = 0; i <= range; i += dial.stepSize) {
                            var angle = (startAngle - i * stepAngle) * Math.PI / 180;
                            var outerX = centerX + radius * Math.cos(angle);
                            var outerY = centerY + radius * Math.sin(angle);
                            var innerX = centerX + (radius - 8) * Math.cos(angle); //adjust tick length
                            var innerY = centerY + (radius - 8) * Math.sin(angle);
                            if (i % 10 === 0) {
                                innerX = centerX + (radius - 15) * Math.cos(angle); //increase length of major ticks
                                innerY = centerY + (radius - 15) * Math.sin(angle);
                            }
                            ctx.beginPath();
                            ctx.moveTo(outerX, outerY);
                            ctx.lineTo(innerX, innerY);
                            var currentValue = dial.from + i;
                            if (currentValue === Math.round(targetSpeed)) {
                                ctx.strokeStyle = (ramping) ? "#FF0000" : "#00ff00";
                            } else if (ramping && ((currentSpeed > targetSpeed && currentValue >= targetSpeed && currentValue <= currentSpeed) ||
                                                (currentSpeed < targetSpeed && currentValue <= targetSpeed && currentValue >= currentSpeed))) {
                                ctx.strokeStyle = (currentSpeed > targetSpeed) ? "red" : Colors.brand;
                            } else {
                                ctx.strokeStyle =  "#6B6B6A";
                            }
                            
                            ctx.lineWidth = 2;
                            ctx.stroke();

                            if (i % 10 === 0) {// sets number of labels
                                var labelRadius = radius -30; //label position
                                var labelX = centerX + labelRadius * Math.cos(angle) - 10; 
                                var labelY = centerY + labelRadius * Math.sin(angle) + 5;
                                
                                ctx.fillStyle = "white"//"#6B6B6A"; //label color
                                ctx.fillText(currentValue, labelX, labelY);
                            }
                        }
                    }
                }
            }

            // handle: Rectangle {
            //     id: dialHandle 
            //     width: 30
            //     height: 30
            //     radius: 15
            //     color: dial.pressed ?"#4E4F4E": "#3A3B3A" 
            //     border.color: "#eb6600"
            //     border.width: 2
            //     x: dialBackground.x + dialBackground.width / 2 - dialHandle.width / 2
            //     y: dialBackground.y + dialBackground.height / 2 - dialHandle.height / 2
            //         transform: [
            //         Translate {
            //             y: -Math.min(dialBackground.width, dialBackground.height) * 0.5 + dialHandle.height / 2
            //         },
            //         Rotation {
            //             angle: dial.angle
            //             origin.x: dialHandle.width / 2
            //             origin.y: dialHandle.height / 2
            //         }
            //     ]
            // }
                // If the dial handle needs a larger mouse area, we can do this:
                // MouseArea {
                //     id: touchArea
                //     width: parent.width*1.2
                //     height: parent.height*1.2
                //     x: parent.x
                //     y: parent.y
                //     anchors.fill: parent
                //     property point handleCenter: Qt.point(dialHandle.x + dialHandle.width / 2, dialHandle.y + dialHandle.height / 2)

                //     onPressed: {
                //         var dx = dialHandle.x - touchArea.handleCenter.x;
                //         var dy = dialHandle.y - touchArea.handleCenter.y;
                //         // dial.angle = Math.atan2(dy, dx) * 180 / Math.PI;
                //     }

                //     onPositionChanged: {
                //         if (pressed) {
                //             var angle = Math.atan2(dialHandle.y - height / 2, dialHandle.x - width / 2) * 180 / Math.PI;
                //             angle = (angle < 0) ? 360 + angle : angle; 
                //             var normalizedAngle = (angle - 130) % 360;
                //             dial.value = (normalizedAngle / 360) * (dial.to - dial.from) + dial.from;
                //         }
                //     }
                // }
            
    
            Text {
                text: qsTr("%1%").arg(Math.round(dial.value))
                color: "white"
                font.pixelSize: 36
                anchors.centerIn: dial
            }
        }
        Text {
            id: txtParams
            property var speedParams: X1Plus.GcodeGenerator.speed_interpolation
            text:qsTr("Acceleration:\n%1\nFeed rate:\n%2\nTime:\n%3")
                .arg(speedParams.acceleration_magnitude(speedParams.speed_fraction(dial.value)).toFixed(2))
                .arg(speedParams.feed_rate(dial.value).toFixed(2))
                .arg(speedParams.speed_fraction(dial.value).toFixed(1)) 
            color: "white"
            font.pixelSize: 18
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: 20
            
        }
            
        Text {
            id: currentSpeedLabel
            text: speedStr[nearestLevel(PrintManager.currentTask.printSpeed)]
            color: "white"
            font.pixelSize: 18
            anchors.right: currentSpeedPecentage.left
            anchors.top:currentSpeedPecentage.top
            anchors.rightMargin: 20
            anchors.topMargin:5
        }
        Text {
            id: currentSpeedPecentage
            text:("%1%").arg(Math.round(PrintManager.currentTask.printSpeed))
            color: "white"
            font.pixelSize: 36
            anchors.left: parent.left
            anchors.leftMargin: 120
            anchors.bottom: dial.top
            anchors.bottomMargin: 20
        }
        
        Text {
            id: targetSpeedLabel
            text: speedStr[nearestLevel(dial.value)]
            color: Colors.brand
            font.pixelSize: 18
            anchors.left: targetSpeedPercent.right
            anchors.leftMargin: 20
            anchors.top:targetSpeedPercent.top
            anchors.topMargin:5
        }
        Text {
            id: targetSpeedPercent
            text: ("%1%").arg(Math.round(targetSpeed))
            color: Colors.brand
            font.pixelSize: 36
            anchors.right: parent.right
            anchors.rightMargin: 120
            anchors.bottom: dial.top
            anchors.bottomMargin: 20

        }   
        Item {
            id: buttonsContainer
            width: parent.width
            height: 170
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: dial.bottom
            anchors.topMargin: 30
            
            Row {
                spacing: 15 
                anchors.horizontalCenter: parent.horizontalCenter      
                visible:true       
                Rectangle {
                    id: rampButton
                    width: 145+70
                    height: 125
                    color: (ramping) ? "#2F302F": Colors.gray_600
                    radius: 25
            
                    Text {
                        text: "Cancel"//(ramping) ? qsTr("Ramp: ON") : qsTr("Ramp: OFF")
                        anchors.centerIn: parent
                        color: "white"
                        font.pixelSize: 30 
                    }
                    
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            // ramping = !(ramping);
                            // let range = Math.abs(PrintManager.currentTask.printSpeed-targetSpeed);
                            // let delta = 2;
                            // dialCanvas.requestPaint();
                            // if (ramping){
                            //     let curr = (X1Plus.emulating) ? 100 : layerNum;
                            //     let tot = (X1Plus.emulating) ?  200 : totalLayerNum;
                            //     var tar = 0;
                            //     if (curr == tot || tot <= 1 || range <= 1){
                            //         ramping = false;
                            //         X1Plus.Bindings.printerStatus.setRamp([]);
                            //         targetSpeed = PrintManager.currentTask.printSpeed;
                            //         return;
                            //     } else {
                            //         for (let i = 0; i < tot; ++i){
                            //             if ((tot - curr) % delta == 0) {
                            //                 break;
                            //             } else {
                            //                 delta += 1;
                            //             }
                            //         }
                            //         tar = curr + range/delta;
                            //         X1Plus.Bindings.printerStatus.setRamp([curr,tar,PrintManager.currentTask.printSpeed,targetSpeed,delta]);
                                    // console.log(curr,tar,PrintManager.currentTask.printSpeed,targetSpeed,delta);
                                parent.parent.parent.parent.parent.parent.target = null;
                                targetSpeed = currentSpeed;
                        }  
                        onEntered: parent.opacity = 0.8
                        onExited: parent.opacity = 1.0
                    }
                }
                Rectangle {
                    width: 1
                    height: 105*.85
                    anchors.verticalCenter: parent.verticalCenter
                }
                Rectangle {
                    id: applyButton
                    width: 145+70
                    height: 125
                    color: Colors.gray_600
                    radius: 25

                    Text {
                        text: qsTr("Apply")
                        anchors.centerIn: parent
                        color: "white"
                        font.pixelSize: 30
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            let gcode = X1Plus.GcodeGenerator.printSpeed(targetSpeed)
                            console.log(gcode);
                            X1Plus.sendGcode(gcode);
                            parent.parent.parent.parent.parent.parent.target = null;
                        }
                    }
                }
            }
        }
    }
}