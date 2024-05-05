import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import QtQuick.Controls 2.12

import "qrc:/uibase/qml/widgets"
import ".."

import '../X1Plus.js' as X1Plus

Item {
    id: tempgraph
    property var samples: X1Plus.TempGraph.samples()
    
    onSamplesChanged: {
        canvas.requestPaint();
    }
    
    Canvas {
        id: canvas
        width: parent.width
        height: parent.height
        
        onPaint: {
            var XRES = canvas.width;
            var YRES = canvas.height;
            var N_SAMPLES = X1Plus.TempGraph.N_SAMPLES;
            
            if (width < 500) {
                /* HMS panel is present */
                if (N_SAMPLES > 5 * 60) {
                    N_SAMPLES = 5 * 60;
                }
            }

            var WPLOT = XRES - 95;
            var HPLOT = YRES - 80;

            var MAXT = 325;
            var MINT = 0;

            var ctx = getContext("2d");
            ctx.clearRect(0, 0, XRES, YRES);

            const LOG_SKEW = 25; // adjust the knee of the logarithm
            const k0 = 1.0 / Math.log(N_SAMPLES + LOG_SKEW);
            const k1 = 1.0 / (1 - Math.log(LOG_SKEW + 1) * k0);
            function to_xc(sampn) {
                /* output: len(sampn) - 1 is at 1.0, len(sampn) - N_SAMPLES is at 0.0 */
                // (1 - (log(N_SAMPLES + LOG_SKEW - x)) / log(N_SAMPLES + LOG_SKEW)) / (1 - log(LOG_SKEW + 1) / log(N_SAMPLES + LOG_SKEW));
                return (1 - (Math.log(N_SAMPLES + LOG_SKEW - sampn)) * k0) * k1 * WPLOT;
            }
            
            function to_yc(tempc) {
                return HPLOT - HPLOT / (MAXT - MINT) * (tempc - MINT);
            }
            
            //ctx.fillStyle = 'rgba(66, 68, 65, 1.0)';
            //ctx.fillRect(0, 0, XRES, YRES);
            
            ctx.save();
            ctx.translate(75, 16);

            // put the text BEFORE we clip
            function put_xlbl(f, txt) {
                if (f < 0)
                    return;
                ctx.strokeStyle = 'rgba(128, 128, 128, 1.0)';
                ctx.beginPath();
                ctx.moveTo(to_xc(f), HPLOT);
                ctx.lineTo(to_xc(f), HPLOT + 15);
                ctx.stroke();

                ctx.fillStyle = 'rgba(192, 192, 192, 1.0)';
                ctx.textBaseline = 'top';
                ctx.textAlign = 'center';
                ctx.font = '20px \"HarmonyOS Sans SC\"';
                ctx.fillText(txt, to_xc(f), HPLOT + 20);
            }
            put_xlbl(N_SAMPLES - 10, "-10s")
            put_xlbl(N_SAMPLES - 30, "-30s")
            put_xlbl(N_SAMPLES - 60, "-1min")
            put_xlbl(N_SAMPLES - 120, "-2min")
            put_xlbl(N_SAMPLES - 5*60, "-5min")
            put_xlbl(N_SAMPLES - 10*60, "-10min")
            put_xlbl(N_SAMPLES - 15*60, "-15min")

            function put_ylbl(db) {
                ctx.fillStyle = 'rgba(192, 192, 192, 1.0)';
                ctx.textBaseline = 'middle';
                ctx.textAlign = 'right';
                ctx.font = '20px \"HarmonyOS Sans SC\"';
                ctx.fillText(i + "°C", -10, to_yc(db));
            }
            for (var i = MINT; i <= MAXT; i += 50) {
                put_ylbl(i);
            }

            ctx.beginPath();
            /* QML canvas2d does not have ctx.roundRect, so we suffer */
            const RADIUS = 25;
            ctx.moveTo(RADIUS, 0);
            ctx.lineTo(WPLOT - RADIUS, 0);
            ctx.arc(WPLOT - RADIUS, RADIUS, RADIUS, -Math.PI / 2, 0);
            ctx.lineTo(WPLOT, HPLOT - RADIUS);
            ctx.arc(WPLOT - RADIUS, HPLOT - RADIUS, RADIUS, 0, Math.PI / 2);
            ctx.lineTo(RADIUS, HPLOT);
            ctx.arc(RADIUS, HPLOT - RADIUS, RADIUS, Math.PI / 2, Math.PI);
            ctx.lineTo(0, RADIUS);
            ctx.arc(RADIUS, RADIUS, RADIUS, Math.PI, 3 * Math.PI / 2);
            ctx.clip();
            
            ctx.fillStyle = 'rgba(40, 40, 40, 1.0)';
            ctx.fill();

            // plot a graticule
            ctx.strokeStyle = 'rgba(80, 80, 80, 1.0)';
            ctx.beginPath();
            for (var i = MINT; i <= MAXT; i += 50) {
                ctx.moveTo(0, to_yc(i));
                ctx.lineTo(WPLOT, to_yc(i));
            }
            ctx.stroke();

            ctx.strokeStyle = 'rgba(80, 80, 80, 1.0)';
            ctx.beginPath();
            var breaks = [-60, -2*60, -3*60, -4*60, -5*60, -6*60, -7*60, -8*60, -9*60, -10*60];
            for (var i in breaks) {
                ctx.moveTo(to_xc(breaks[i] + N_SAMPLES), 0);
                ctx.lineTo(to_xc(breaks[i] + N_SAMPLES), HPLOT);
            }
            ctx.stroke();

            var minsamp = N_SAMPLES - samples.length;
            if (minsamp < 0)
                minsamp = 0;

            var sxs = [];
            for (var i = minsamp; i < samples.length; i++) {
                sxs.push(to_xc(i + N_SAMPLES - samples.length));
            }

            /* plot nozzle setpoint */
            ctx.fillStyle = 'rgba(192, 128, 128, 0.2)';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(sxs[minsamp], to_yc(MINT));
            for (var i = minsamp; i < samples.length; i++) {
                ctx.lineTo(sxs[i], to_yc(samples[i][1]));
            }
            ctx.lineTo(sxs[samples.length-1], to_yc(MINT));
            ctx.lineTo(sxs[minsamp], to_yc(MINT));
            
            ctx.fill();

            /* plot bed setpoint */
            ctx.fillStyle = 'rgba(128, 128, 192, 0.2)';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(sxs[minsamp], to_yc(MINT));
            for (var i = minsamp; i < samples.length; i++) {
                ctx.lineTo(sxs[i], to_yc(samples[i][3]));
            }
            ctx.lineTo(sxs[samples.length-1], to_yc(MINT));
            ctx.lineTo(sxs[minsamp], to_yc(MINT));
            ctx.fill();
            
            /* plot nozzle temps */
            ctx.strokeStyle = 'rgba(255, 192, 192, 0.7)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            for (var i = minsamp; i < samples.length; i++) {
                ctx.lineTo(sxs[i], to_yc(samples[i][minsamp]));
            }
            ctx.stroke();

            /* plot bed temps */
            ctx.strokeStyle = 'rgba(192, 192, 255, 0.7)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            for (var i = minsamp; i < samples.length; i++) {
                ctx.lineTo(sxs[i], to_yc(samples[i][2]));
            }
            ctx.stroke();

            /* plot chamber temps */
            ctx.strokeStyle = 'rgba(192, 255, 192, 0.7)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            for (var i = minsamp; i < samples.length; i++) {
                ctx.lineTo(sxs[i], to_yc(samples[i][4]));
            }
            ctx.stroke();
            ctx.restore();
        }
    }
}
