import QtQuick 2.0
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0

import "qrc:/uibase/qml/widgets"
import ".."

import "../X1Plus.js" as X1Plus

Item {
    id: statscomp
    property string devName:DeviceManager.build.name
    property string devSer:DeviceManager.build.seriaNO
    property var maintainInfo: {
        "carbon_rods": {
            "abs_last_print_time": 0,
            "asa_last_print_time": 0,
            "user_notified": false
        },
        "lead_screws": {
            "last_record_timestamp": 0,
            "user_notified": false
        }
    }

    Component.onCompleted:{
        
    }

    MarginPanel {
        id: title
        height: 68 + 39 + 30
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
                width: titlePanel.height
                height: brandImage.width
                source: "../../icon/product_icon.svg"
            }

            Text {
                id: titleName
                anchors.left: brandImage.right
                anchors.leftMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                color: Colors.gray_200
                font: Fonts.body_36
                text: qsTr("%1: Device Info").arg(devName.replace(/[\r\n]+/g, ''))
            }

            ZButton {
                id: returnBtn
                anchors.right: parent.right
                anchors.rightMargin: 28
                anchors.top: parent.top
                anchors.topMargin: 6
                checked: false
                text: qsTr("Return")
                onClicked: { pageStack.pop() }
            }
        }
    }


    MarginPanel {
        id: infosPanel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        leftMargin: 26
        rightMargin: 26
        bottomMargin: 26
        radius: 15
        color: Colors.gray_600

        Component.onCompleted: {
            populateStatsList();
        }

        // XXX: This should find a home some day, but right now I haven't got one for it.
        /*        
        Text {
            id: clockText
            text: Qt.formatDateTime(new Date(), "hh:mm:ss") + " UTC"
            anchors.verticalCenter: titleLabel.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: 20
            font: Fonts.head_30
            color: Colors.gray_200
        }

        Timer {
            interval: 1000
            repeat: true
            running: true
            onTriggered: {
                clockText.text = Qt.formatDateTime(new Date(), "hh:mm:ss") + " UTC"
            }
        }
        */

        Item {
            id: stepItem
            anchors.fill: parent
            anchors.topMargin: 36
            anchors.bottomMargin: 36
            anchors.leftMargin: 36
            anchors.rightMargin: 46
            ListModel{
                id:statsListModel
            }
            ListView {
                id: statsList
                anchors.fill: parent
                boundsBehavior: Flickable.StopAtBounds
                interactive: true
                ScrollBar.vertical: ScrollBar {
                    policy: statsList.contentHeight > statsList.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                    interactive: true
                }
                spacing: 5
                model: statsListModel
                clip: true
                delegate:Item {
                    height: diagRes.implicitHeight + 5
                    Text {
                        id: diagRes
                        width: stepItem.width
                        font: Fonts.body_24
                        color: Colors.gray_100
                        wrapMode: Text.WordWrap
                        text: {
                             if (statsListModel.count < 1) {
                                return "";

                             } else {
                                return leftText + " <font size=\"3\" color=\"#AEAEAE\">" + rightText + "</font>";
                             }
                        }
                        onLinkActivated: { 
                            let newDate = Math.floor(Date.now()/1000);
                            if (link == "carbon"){
                                console.log("[x1p] Reset carbon rod maintenance date");
                                DeviceManager.maintain.carbon = true;
                            } else if (link == "screws"){
                                console.log("[x1p] Reset leadscrew maintenance date");
                                DeviceManager.maintain.screws = true;
                            }
                            statsListModel.set(index, {leftText: model.leftText, rightText: formatDate(newDate)});
                        }
                    }
                }
            }
        }
    }
 
    
    function getMostRecentDate(filePath) {
        const data = X1Plus.loadJson(filePath);
        if (data && data.dates && Array.isArray(data.dates)) {
            const sortedDates = data.dates.sort((a, b) => new Date(b) - new Date(a));
            const mostRecentDate = new Date(sortedDates[0]);
            return mostRecentDate.toLocaleString('en-US', {
                year: 'numeric', 
                month: 'short', 
                day: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit', 
                hour12: false
            });
        } else {
            return null;
        }
    }

    function formatDate(timestamp) {
        const date = new Date(timestamp * 1000);

        const options = { month: 'short', day: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false };
        return date.toLocaleString('en-US', options);
    }

    function populateStatsList() {
        statsListModel.clear(); 
        try {
            var serialNo = DeviceManager.build.seriaNO;
            let forward_info = X1Plus.loadJson("/config/forward/info");
            let filament_info = X1Plus.loadJson("/config/forward/filament_info");
            let maintain_info = X1Plus.loadJson("/config/forward/maintain_info");
            
            let totalPrintTime = (parseFloat(forward_info.print_time) / 3600).toFixed(2);
            statsListModel.append({"leftText": qsTr("Printer serial number: "), "rightText": serialNo.toString()});
            statsListModel.append({"leftText": qsTr("Total print time: "), "rightText": qsTr("%1 hours").arg(totalPrintTime)});
            //maintenance timestamps
            if (maintain_info && maintain_info.lead_screws) {
                function mkResetLink(tipo) {
                    return "&nbsp;(<font size=\"3\" color=\"#05ae4b\"><a href='" + tipo +"'>" + qsTr("reset") + "</a></font>)";
                }
                statsListModel.append({"leftText": qsTr("Lead screws last lubricated: "), "rightText": formatDate(maintain_info.lead_screws.last_record_timestamp) + mkResetLink('screws')});
                let absTime = maintain_info.carbon_rods.abs_last_print_time;
                let asaTime = maintain_info.carbon_rods.asa_last_print_time;
                if (asaTime > 0) {
                    statsListModel.append({"leftText": qsTr("ASA carbon rod maintenance timer: "), "rightText": formatDate(asaDate) + mkResetLink('carbon')});
                }
                if (absTime > 0) {
                    statsListModel.append({"leftText": qsTr("ABS carbon rod maintenance timer: "), "rightText": formatDate(absDate) + mkResetLink('carbon')});
                }
            }
            
            //calibration timestamps
            var data = getMostRecentDate("/mnt/sdcard/x1plus/printers/"+devSer+"/logs/mesh_data.json");
            if (data != null){
                statsListModel.append({"leftText": qsTr("Bed mesh calibrated: "), "rightText": data});
            }
            data = getMostRecentDate("/mnt/sdcard/x1plus/printers/"+devSer+"/logs/vibration_comp.json");
            if (data != null){
                statsListModel.append({"leftText": qsTr("Vibration compensation calibrated: "), "rightText": data});
            }
            
            //filament_info
            if (filament_info && filament_info.ams_array && filament_info.ams_array.length > 0) {
                statsListModel.append({"leftText": qsTr("AMS total length: "), "rightText": qsTr("%1 meters").arg((filament_info.ams_array[0].ams_total_length).toFixed(2))});
                statsListModel.append({"leftText": qsTr("AMS total print time: "), "rightText": qsTr("%1 hours").arg((parseFloat(filament_info.ams_array[0].ams_total_print_time) / 3600).toFixed(2)) });
                statsListModel.append({"leftText": qsTr("AMS total filament switches: "), "rightText": qsTr((filament_info.ams_array[0].ams_total_switch_filament_cnt).toFixed(0))});
                statsListModel.append({"leftText": qsTr("AMS total failed filament switches: "), "rightText": qsTr((filament_info.ams_array[0].ams_total_switch_filament_fail_cnt).toFixed(0))});
                for (var i = 0; i < 4; i++) {
                    statsListModel.append({"leftText": qsTr("Tray %1 print time: ").arg(i+1), "rightText": qsTr("%1 hours").arg((parseFloat(filament_info.ams_array[0].tray[i].print_time) / 3600).toFixed(2))});
                    statsListModel.append({"leftText": qsTr("Tray %1 filament switches: ").arg(i+1), "rightText": qsTr((filament_info.ams_array[0].tray[i].switch_filament_cnt).toFixed(0))});
                    statsListModel.append({"leftText": qsTr("Tray %1 failed filament switches: ").arg(i+1), "rightText": qsTr((filament_info.ams_array[0].tray[i].switch_filament_fail_cnt).toFixed(0))});
                    statsListModel.append({"leftText": qsTr("Tray %1 print length: ").arg(i+1), "rightText": qsTr("%1 meters").arg(qsTr((filament_info.ams_array[0].tray[i].tray_total_length).toFixed(2))});
                }

                filament_info.virtual_tray.filament_info.forEach(ftype => {
                    var filType = Object.keys(ftype)[0];
                    var filLength = parseFloat(ftype[filType]).toFixed(2);
                    var printTime = (parseFloat(ftype.print_time)/3600).toFixed(2);
                    if (filType !== "print_time"){
                        statsListModel.append({"leftText": qsTr("%1 - print time: ").arg(filType), "rightText": qsTr("%1 hours").arg(printTime)});
                        statsListModel.append({"leftText": qsTr("%1 - print length: ").arg(filType), "rightText": qsTr("%1 meters").arg(filLength)});
                    }
                });
            }
        } catch (e) {
            console.log("Error in populateStatsList: " + e);
            console.log(e.stack || e.stacktrace || "no stack trace");
        }
    }
}
