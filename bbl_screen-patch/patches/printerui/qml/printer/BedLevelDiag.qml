import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import QtQuick.Controls 2.12
import X1PlusNative 1.0
import "qrc:/uibase/qml/widgets"
import "../X1Plus.js" as X1Plus
import ".."

Item {
    id: bedleveldiag
    property var calibrationData: null
    property var mesh: calibrationData && calibrationData.mesh
    property string plotTitle: calibrationData && X1Plus.formatTime(calibrationData.time) || ""
    
    onMeshChanged: {
        if (mesh) {
            canvas.requestPaint();
        }
    }

    MarginPanel {
        id: diagnosticPanel
        width: 382
        anchors.left: parent.left
        anchors.top:  parent.top
        anchors.bottom: parent.bottom
        leftMargin: 26
        topMargin: 26
        bottomMargin: 26
        Text {
            id: guidelabel
            anchors.top: parent.top
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            font: Fonts.head_36
            color: Colors.brand
            text: qsTr("Bed Diagnostics")
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
            anchors.right: parent.right
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10

            Text{
                function hilite(t) {
                    return `<font color="#93C47D">${t}</font>`;
                }

                id:diagRes
                wrapMode:Text.WordWrap
                color: Colors.gray_100
                font: Fonts.body_24
                //height: diagRes.implicitHeight+10
                anchors.top: parent.top
                anchors.left:parent.left
                anchors.right: parent.right
                
                text: calibrationData ?
                    qsTr("<font size='3' color='#AEAEAE'>This calibration run was captured on %1, at a bed temperature of %2.<br><br>" +
                        "Detected bed tilt was %3 across the X axis, and %4 across the Y axis. " +
                        "The bed had a peak-to-peak deviation of %5, and remaining nonplanarity after perfectly tramming the bed would be %6.<br><br>")
                    .arg(hilite(plotTitle))
                    .arg(hilite(calibrationData.temperature.toFixed(0).toString() + "°C"))
                    .arg(hilite(calibrationData.bedMetrics.tiltX.toFixed(2).toString() + " mm"))
                    .arg(hilite(calibrationData.bedMetrics.tiltY.toFixed(2).toString() + " mm"))
                    .arg(hilite(calibrationData.bedMetrics.peakToPeak.toFixed(2).toString() + " mm"))
                    .arg(hilite(calibrationData.bedMetrics.nonplanarity.toFixed(2).toString() + " mm")) +
                    X1Plus.MeshCalcs.describeMetrics(calibrationData.bedMetrics)
                    : ""
            }
        }

    }

    MarginPanel {
        id: caliPanel
        anchors.left: diagnosticPanel.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        leftMargin: 14
        rightMargin: 26
        topMargin: diagnosticPanel.topMargin
        bottomMargin: diagnosticPanel.bottomMargin
        ZButton { 
            id: deleteBtn
            icon: "../../icon/components/trash.svg"
            iconSize: 50
            width: 50
            type: ZButtonAppearance.Secondary
            anchors.right:parent.right
            anchors.rightMargin:10
            anchors.top:caliPanel.top
            anchors.topMargin:5
            cornerRadius:width/2            
            onClicked: {
                dialogStack.popupDialog(
                        "TextConfirm", {
                            name: "clear calibration logs",
                            type: TextConfirm.YES_NO,
                            defaultButton: 0,
                            text: `Are you sure you want to remove the data entry from ${plotTitle}?`,
                            onYes: function() {
                                X1Plus.BedMeshCalibration.deleteEntry(calibrationData.time);
                                bedleveldiag.parent.pop();
                            }
                        });
            }
        }
 
        Canvas {
    	id: canvas
        //514
        width:667
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
            if (!mesh){
                return;
            }
    	    console.log("[x1p] Rendering bed mesh", mesh, JSON.stringify(mesh));

            ctx.clearRect(0,0,canvas.width,canvas.height);
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
            

            var minh = 0;
            var maxh = 0;
            for (var y in mesh) {
                for (var x in mesh[y]) {
                    if (mesh[y][x] < minh) minh = mesh[y][x];
                    if (mesh[y][x] > maxh) maxh = mesh[y][x];
                }
            }
            var range = Math.max(Math.abs(minh), Math.max(maxh), 0.8);

            for (var y in mesh) {
                for (var x in mesh[y]) {
                    var v = mesh[y][x];
                    var rangec = Math.floor((1 - Math.abs(v) / range) * 255);
                    if (v > 0)
                        ctx.fillStyle = 'rgba(255, ' + rangec + ', ' + rangec + ', 1.0)';
                    else
                        ctx.fillStyle = 'rgba(' + rangec + ', ' + rangec + ', 255, 1.0)';
                    ctx.beginPath();
                    ctx.arc(parseFloat(x), YBED - parseFloat(y), 8, 0, 2*Math.PI);
                    ctx.fill();
                }
            }

            // draw a scale
            var gradient = ctx.createLinearGradient(0, 0, 0, YBED);
            var rangec = Math.floor((1 - maxh / range) * 255);
            gradient.addColorStop(0, 'rgba(255, ' + rangec + ', ' + rangec + ', 1.0)');
            var midpt = maxh / (maxh - minh + 0.001);
            gradient.addColorStop(midpt, 'rgba(255, 255, 255, 1.0)');
            rangec = Math.floor((1 - Math.abs(minh) / range) * 255);
            gradient.addColorStop(1, 'rgba(' + rangec + ', ' + rangec + ', 255, 1.0)');

            ctx.fillStyle = gradient;
            ctx.strokeStyle = 'white';
            ctx.fillRect(XBED + 10, 0, 20, YBED);
            ctx.strokeRect(XBED + 10, 0, 20, YBED);
            
            ctx.fillStyle = 'white';
            ctx.textBaseline = 'top';
            ctx.fillText(maxh.toFixed(2) + "mm", XBED + 35, 0);
            
            // don't render 0.00mm if it's right up against an existing label
            if (midpt > 0.1 && midpt < 0.9) {
                ctx.textBaseline = 'middle';
                ctx.fillText("0.00mm", XBED + 35, YBED * midpt);
            }
            
            ctx.textBaseline = 'bottom';
            ctx.fillText(minh.toFixed(2) + "mm", XBED + 35, YBED);
            
            ctx.restore();
    	    }
            
        }
    }
    Item {
        X1PBackButton {
            onClicked: { 
                pageStack.pop()
            }
        }
    }
}
