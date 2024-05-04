import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import "."

Rectangle {
    width: 103
    height: 103
    color: Colors.gray_500
    
    ZImage {
        id: wifiIcon
        width: 70 
        height: 70
        anchors.centerIn: parent
        fillMode: Image.PreserveAspectFit 
        originSource: "../image/wifi_0.svg"
    }
    MouseArea {
        anchors.fill:parent
        onClicked: {
            updateIcon(); /* placeholder mousearea - this could open wifi setup or more details about the network */
        }
        onEntered: wifiIcon.opacity = 0.8
        onExited: wifiIcon.opacity = 1.0
    }
    Timer {
        id: wifiTimer
        running: true
        interval: 10000
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            updateIcon();
        }
    }
    function updateIcon(){
        /* the jankiest of jank.. but doing this in C++ seemed overkill */
        let dBmString = X1PlusNative.popen("cat /proc/net/wireless | sed -n 3p | awk '{print $4}' | sed 's/.$//'").trim();
        let dBm = parseInt(dBmString, 10);
        if (isNaN(dBm)) {
            return; 
        }
        let x_norm = dBm + 100;
        if (x_norm < 1) x_norm = 1;
        let y = Math.round((3 * Math.log10(x_norm)) / Math.log10(101));
        y = Math.max(0, Math.min(3, y)); 

        let iconPath = `../image/wifi_${y}.svg`;
        if (wifiIcon.source !== iconPath) {
            wifiIcon.source = iconPath;
        }
    }
}

