import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import QtQuick.Controls 2.12

import "qrc:/uibase/qml/widgets"
import ".."

import '../X1Plus.js' as X1Plus


Item {
    id: vibcompplotter
    property var calibrationData: null
    property string plotTitle: calibrationData && X1Plus.formatTime(calibrationData.time) || ""

    onCalibrationDataChanged: {
        if (calibrationData) {
            scatterPlotCanvas.requestPaint();
        }
    }

    MarginPanel {
        id: caliPanel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        leftMargin: 26
        rightMargin: 26
        topMargin: 26
        bottomMargin: 26

        
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
                            text: qsTr("Are you sure you want to remove the data entry from %1?").arg(plotTitle),
                            onYes: function() {
                                X1Plus.ShaperCalibration.deleteEntry(calibrationData.time);
                                vibcompplotter.parent.pop();
                            }
                        });
            }
        }

        Text {
			id: plotTitleLabel
			anchors.top: parent.top
			anchors.topMargin: 25
			anchors.horizontalCenter: parent.horizontalCenter
			font: Fonts.head_24
			color: Colors.brand
			text: ""
            }   
           Canvas {
            id: scatterPlotCanvas
            width:1030
            height:590
            anchors.top: plotTitleLabel.bottom
            anchors.topMargin: 10
            anchors.horizontalCenter: parent.horizontalCenter

            onPaint: {
                var ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);
                var colors = ["blue","red"]

				var XRES = width;
				var YRES = height;

				var WPLOT = 870;
				var HPLOT = 450;

				var PLOTOFS = 40;

				var AX0COLOR = 'rgba(192, 255, 192, 1.0)';
				var AX1COLOR = 'rgba(192, 192, 255, 1.0)';

				function render(ctx, vibe) {
					//ctx.fillStyle = 'rgba(66, 68, 65, 1.0)';
					//ctx.fillRect(0, 0, XRES, YRES);
					
					ctx.save();
					ctx.translate(85, 80);
					
					ctx.fillStyle = 'rgba(40, 40, 40, 1.0)';
					ctx.fillRect(0, 0, WPLOT, HPLOT);

					var dbmin = 0;
					var dbmax = 0;
					var fmin = Infinity;
					var fmax = -Infinity;
					for (var ax in vibe.axes) {
						for (var pt in vibe.axes[ax].points) {
							var f = parseInt(pt);
							var a = vibe.axes[ax].points[pt].a;
							// would be nice to do some outlier rejection here, maybe by
							// standard deviation, weighted by 1/log(f)
							dbmin = Math.min(dbmin, a);
							dbmax = Math.max(dbmax, a);
							fmin = Math.min(fmin, f);
							fmax = Math.max(fmax, f);
						}
					}
					var fmin_log = Math.log(fmin);
					var fmax_log = Math.log(fmax);
					
					/* convert x to a log scale */
					function to_xc(f) {
						return ((Math.log(f) - fmin_log) / (fmax_log - fmin_log)) * WPLOT;
					}
					
					function to_yc(db) {
						/* positive dB towards the top */
						return HPLOT - (db - dbmin) / (dbmax - dbmin) * HPLOT;
					}

					// plot a graticule
					ctx.strokeStyle = 'rgba(80, 80, 80, 1.0)';
					ctx.beginPath();
					for (var i = 0; i < dbmax; i += 10) {
						ctx.moveTo(0, to_yc(i));
						ctx.lineTo(WPLOT, to_yc(i));
					}
					for (var i = 0; i > dbmin; i -= 10) {
						ctx.moveTo(0, to_yc(i));
						ctx.lineTo(WPLOT, to_yc(i));
					}
					ctx.stroke();
					
					function put_ylbl(db) {
						ctx.fillStyle = 'rgba(192, 192, 192, 1.0)';
						ctx.textBaseline = 'middle';
						ctx.textAlign = 'right';
						ctx.font = '20px sans-serif';
						ctx.fillText(i + " dB", -10, to_yc(db));
					}
					for (var i = 0; i < dbmax; i += 10) {
						put_ylbl(i);
					}
					for (var i = 0; i > dbmin; i -= 10) {
						put_ylbl(i);
					}

					ctx.strokeStyle = 'rgba(128, 128, 128, 1.0)';
					ctx.beginPath();
					var breaks = [20, 30, 40, 50, 60, 70, 80, 90, 100, 200];
					for (var i in breaks) {
						ctx.moveTo(to_xc(breaks[i]), 0);
						ctx.lineTo(to_xc(breaks[i]), HPLOT);
					}
					ctx.stroke();

					// this kind of sucks that I do it by hand here but oh well...  sort
					// of annoyingly fidgety
					ctx.setLineDash([2, 5]);
					ctx.lineWidth = 2;
					ctx.textBaseline = 'bottom';
					ctx.textAlign = 'center';
					ctx.font = '20px sans-serif';

					ctx.strokeStyle = AX0COLOR;
					ctx.beginPath()
					ctx.moveTo(to_xc(vibe.axes.x.summaries[0].wn), -40);
					ctx.lineTo(to_xc(vibe.axes.x.summaries[0].wn), HPLOT);
					ctx.stroke();

					ctx.strokeStyle = AX1COLOR;
					ctx.beginPath()
					ctx.moveTo(to_xc(vibe.axes.y.summaries[0].wn), -10);
					ctx.lineTo(to_xc(vibe.axes.y.summaries[0].wn), HPLOT);
					ctx.stroke();

					ctx.fillStyle = AX0COLOR;
					ctx.fillText(vibe.axes.x.summaries[0].wn.toFixed(0) + " Hz", to_xc(vibe.axes.x.summaries[0].wn), -45);

					ctx.fillStyle = AX1COLOR;
					ctx.fillText(vibe.axes.y.summaries[0].wn.toFixed(0) + " Hz", to_xc(vibe.axes.y.summaries[0].wn), -15);
					
					ctx.setLineDash([200000]); // setLineDash([]) does not work on qml??
					
					function put_xlbl(f) {
						ctx.strokeStyle = 'rgba(128, 128, 128, 1.0)';
						ctx.beginPath();
						ctx.moveTo(to_xc(f), HPLOT);
						ctx.lineTo(to_xc(f), HPLOT + 15);
						ctx.stroke();

						ctx.fillStyle = 'rgba(192, 192, 192, 1.0)';
						ctx.textBaseline = 'top';
						ctx.textAlign = 'center';
						ctx.font = '20px sans-serif';
						ctx.fillText(f + " Hz", to_xc(f), HPLOT + 20);
					}
					var xlbls = [10, 20, 30, 50, 70, 100,200];
					for (var i in xlbls) {
						put_xlbl(xlbls[i]);
					}
					
					// a nice bold X axis is nice
					ctx.strokeStyle = 'rgba(255, 255, 255, 1.0)';
					ctx.lineWidth = 3;
					ctx.beginPath();
					ctx.moveTo(0, to_yc(0));
					ctx.lineTo(WPLOT, to_yc(0));
					ctx.stroke();
					
					// draw the rest of the owl
					function put_ax(stroke, ax, axname) {
						ctx.strokeStyle = stroke;
						ctx.lineWidth = 3;

						ctx.beginPath();
						var f;
						var fs = Object.keys(ax).map(f => parseInt(f)).sort((a, b) => a - b);
						for (var nf in fs) {
							f = fs[nf];
							ctx.lineTo(to_xc(f), to_yc(ax[f].a));
						}
						ctx.stroke();
						
						ctx.fillStyle = stroke;
						ctx.textAlign = 'left';
						ctx.textBaseline = 'middle';
						ctx.font = '20px sans-serif';
						ctx.fillText(axname, to_xc(f) + 10, to_yc(ax[f].a));
					}
					put_ax(AX0COLOR, vibe.axes.x.points, qsTr("X axis"));
					put_ax(AX1COLOR, vibe.axes.y.points, qsTr("Y axis"));
					ctx.restore();
				}

                if(calibrationData!=null){
                    plotTitleLabel.text = qsTr("Frequency Response Plot: ") + plotTitle;
                    render(ctx, calibrationData);
                }
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
