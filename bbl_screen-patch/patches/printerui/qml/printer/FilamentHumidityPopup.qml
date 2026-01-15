import QtQuick 2.12
import QtQuick.Layouts 1.12
import QtQuick.Shapes 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import ".."
import "../X1Plus.js" as X1Plus

Rectangle {
    radius: 15
    color: Colors.gray_600
    ZText {
        id: humidityTitle
        anchors.top: parent.top
        anchors.topMargin: 24
        color: Colors.gray_200
        font: Fonts.head_30
        anchors.horizontalCenter: parent.horizontalCenter
        text: qsTr("AMS environmental status")
    }

    Rectangle {
        id: humidityRect1
        anchors.top: parent.top
        anchors.topMargin: 67
        color: "#4CD01B1B"
        width: humidityTx1.width + 10
        height: 33
        radius: 6
        anchors.horizontalCenter: parent.horizontalCenter
        visible: currentFeeder.humidity < 3
        ZText {
            id: humidityTx1
            anchors.centerIn: parent
            color: Colors.white_900
            font: Fonts.body_20
            text: qsTr("This AMS's desiccant may need to be replaced.")
        }
    }

    ColumnLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        
        anchors.top: humidityRect1.bottom
        anchors.topMargin: 10
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 29
        spacing: 5
        
        RowLayout {
            spacing: 15
            Layout.fillHeight: true
            Layout.fillWidth: true

            Rectangle {
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                Layout.preferredHeight: 132
                Layout.minimumWidth: 132
                implicitHeight: 132
                implicitWidth: 132
                Layout.fillWidth: true
                color: "transparent"
                ZImage {
                    width: 132
                    height: 132
                    anchors.centerIn: parent
                    sourceSize.width: 132
                    sourceSize.height: 132
                    source: "../../icon/humidity_"+ currentFeeder.humidity +".svg"
                }
            }
            
            ColumnLayout {
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                Layout.fillWidth: true
                spacing: 10
                
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_24
                    color: Colors.gray_300
                    text: qsTr("Temperature")
                }
                
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_48
                    color: Colors.gray_200
                    text: qsTr("%1 °C").arg(parseFloat(currentFeederDDS.temp).toFixed(1))
                }
            }

            ColumnLayout {
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                Layout.fillWidth: true
                spacing: 10
                visible: usingAmsV2Protocol
                
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_24
                    color: Colors.gray_300
                    text: qsTr("Humidity")
                }
                
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_48
                    color: Colors.gray_200
                    text: qsTr("%1% RH").arg(parseFloat(currentFeederDDS.humidity_raw).toFixed(0))
                }
            }
        }

        ZImage {
            id: humidityTxImg2
            source: "../../image/humidity_help.svg"

            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter

            Text {
                id: dryTx
                anchors.left: parent.left
                anchors.leftMargin: 38
                anchors.verticalCenter: parent.verticalCenter
                color: "#7FFFFFFF"
                font: Fonts.head_22
                text: qsTr("DRY")
            }
            Text {
                id: wetTx
                anchors.right: parent.right
                anchors.rightMargin: 32
                anchors.verticalCenter: parent.verticalCenter
                color: "#7FFFFFFF"
                font: Fonts.head_22
                text: qsTr("WET")
            }
        }

        Text {
            id: humidityTx
            Layout.fillWidth: true
            color: Colors.gray_300
            font: Fonts.body_24
            wrapMode: Text.WordWrap
            visible: usingAmsV2Protocol
            text: qsTr("Environmental sensors on the first-generation AMS may not be accurate.  The AMS provides these values, but original firmware never exposes them to the user.  Take them with a grain of salt!")
        }

        RowLayout {
            spacing: 20
            Layout.fillHeight: true
            Layout.fillWidth: true
            visible: !usingAmsV2Protocol
            
            Rectangle {
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                Layout.preferredHeight: 80
                Layout.minimumWidth: 80
                implicitHeight: 80
                implicitWidth: 80
                Layout.fillWidth: true
                color: "transparent"
                ZImage {
                    width: 80
                    height: 80
                    anchors.centerIn: parent
                    sourceSize.width: 80
                    sourceSize.height: 80
                    source: "../../icon/warning_yellow.png"
                }
            }

            Text {
                Layout.fillWidth: true
                color: Colors.gray_200
                font: Fonts.body_26
                wrapMode: Text.WordWrap
                text: qsTr("This printer's MC firmware is too old to support second-generation AMS units.  Upgrade the MC firmware to enable new AMS features, like drying, humidity in percentage, and correct tray count for AMS HT.")
            }
        }
    }
}