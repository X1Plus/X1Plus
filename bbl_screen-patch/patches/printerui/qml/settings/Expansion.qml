import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0

import "../X1Plus.js" as X1Plus

import "qrc:/uibase/qml/widgets"
import ".."
import "../printer"

/* This can only get triggered if there is an expansion, so we can assume that X1Plus.Expansion.status() is nonnull. */
Item {
    id: top

    MarginPanel {
        id: title
        height: 68 + 39 + 20 + line.height + 20
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
                width: 68
                height: 68
                source: "../../icon/components/cfw.png"
            }

            Text {
                id: titleName
                anchors.left: brandImage.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                color: Colors.gray_200
                font: Fonts.body_36
                text: qsTr("%1 settings").arg(X1Plus.Expansion.productName())
            }

            ZButton {
                id: returnBtn
                anchors.right: parent.right
                anchors.rightMargin: 28
                anchors.top: parent.top
                anchors.topMargin: 6
                checked: false
                text: qsTr("Return")
                onClicked: { parent.parent.parent.parent.pop() }
            }

            Rectangle {
                id: line
                height: 1
                anchors.left: brandImage.left
                anchors.right: parent.right
                anchors.rightMargin: 64
                anchors.top: brandImage.bottom
                anchors.topMargin: 20
                color: Colors.gray_500
            }
        }
    }

    MarginPanel {
        id: expander_graphic_panel
        width: 400
        anchors.top: title.bottom
        anchors.left: parent.left
        leftMargin: 16
        height: 260
        radius: 15
        color: Colors.gray_600

        Text{
            wrapMode:Text.WordWrap
            color: Colors.gray_100
            font: Fonts.body_28
            height: implicitHeight+10
            anchors.top: parent.top
            anchors.topMargin: 30
            anchors.left:parent.left
            anchors.leftMargin: 30
            anchors.right: parent.right
            anchors.rightMargin: 30
            
            text: "[graphic of Expander goes here]"
        }
    }
    
    MarginPanel {
        id: expander_info_panel
        width: 400
        anchors.top: expander_graphic_panel.bottom
        anchors.left: parent.left
        leftMargin: 16
        topMargin: 14
        anchors.bottom: parent.bottom
        bottomMargin: 16
        radius: 15
        color: Colors.gray_600
        
        Text{
            wrapMode:Text.WordWrap
            color: Colors.gray_100
            font: Fonts.body_26
            height: implicitHeight+10
            anchors.top: parent.top
            anchors.topMargin: 30
            anchors.left:parent.left
            anchors.leftMargin: 30
            anchors.right: parent.right
            anchors.rightMargin: 30
            
            text: qsTr("You can customize the behavior of peripherals attached to your %1.  Never add or remove an add-on module while your printer is powered on.").arg(X1Plus.Expansion.productName())
        }
    }

    MarginPanel {
        id: config_panel
        anchors.left: expander_graphic_panel.right
        anchors.right: parent.right
        rightMargin: 16
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        bottomMargin: 15
        leftMargin: 16
        radius: 15
        color: Colors.gray_600
        
        ListView {
            id: configList
            anchors.left: parent.left
            anchors.right: parent.right
            height: parent.height
            clip: true
            model: configItems
            delegate: configComp
        }
    }

    function mk_port_text(port) {
        var portdef = X1Plus.Expansion.status().ports[port];
        if (portdef === undefined)
            return null;
        if (portdef === null)
            return qsTr("No module detected");
        return portdef.model;
    }

    property var configItems: SimpleItemModel {
        DeviceInfoItem { title: qsTr("Expander hardware"); value: X1Plus.Expansion.productName()
            function onClicked() { }
        }

        DeviceInfoItem {
            property var wiredNetwork: X1Plus.Network.wiredNetwork()
            title: qsTr("Ethernet")
            value: (!wiredNetwork || !wiredNetwork.powerState) ? "Ethernet not available" :
                   wiredNetwork.state === Network.DISCONNECTED ? qsTr("Cable not connected") :
                   wiredNetwork.state === Network.CONNECTED ? qsTr("Connected (%1)").arg(wiredNetwork.ipv4) :
                   qsTr("No Internet connection")
            dot: (!wiredNetwork || !wiredNetwork.powerState)
            function onClicked() {
                top.parent.pop();
                Printer.jumpTo("Settings/Network");
            }
        }

        DeviceInfoItem { title: qsTr("Port A"); value: mk_port_text("port_a"); hidden: X1Plus.Expansion.status().ports["port_a"] === undefined; function onClicked() { dialogStack.popupDialog('../settings/ExpanderAddonDialog', { port: "a" }); } }
        DeviceInfoItem { title: qsTr("Port B"); value: mk_port_text("port_b"); hidden: X1Plus.Expansion.status().ports["port_b"] === undefined; function onClicked() { dialogStack.popupDialog('../settings/ExpanderAddonDialog', { port: "b" }); } }
        DeviceInfoItem { title: qsTr("Port C"); value: mk_port_text("port_c"); hidden: X1Plus.Expansion.status().ports["port_c"] === undefined; function onClicked() { dialogStack.popupDialog('../settings/ExpanderAddonDialog', { port: "c" }); } }
        DeviceInfoItem { title: qsTr("Port D"); value: mk_port_text("port_d"); hidden: X1Plus.Expansion.status().ports["port_d"] === undefined; function onClicked() { dialogStack.popupDialog('../settings/ExpanderAddonDialog', { port: "d" }); } }

        DeviceInfoItem { title: qsTr("I²C (STEMMA)"); value: qsTr("Port in use by expansion module"); function onClicked() { } }
        
        // there must always be at least one unhidden item at the bottom to
        // keep the line splitter looking right
        DeviceInfoItem { title: qsTr("USB"); value: qsTr("Unsupported in current version") }
    }
    
    
    Component {
        id: configComp

        Rectangle {
            width: ListView.view.width
            height: modelData.hidden ? 0 : 75
            color: modelData.onClicked === undefined ? "transparent" : backColor.color
            radius: 15
            visible: !modelData.hidden

            ZLineSplitter {
                alignment: Qt.AlignTop
                padding: 23
                color: "#606060"
                visible: index > 0
            }

            Item {
                height: parent.height
                anchors.left: parent.left
                anchors.leftMargin: 36
                anchors.right: parent.right
                anchors.rightMargin: 36

                Rectangle {
                    width: parent.width
                    height: 1
                    anchors.bottom: parent.bottom
                    color: "#606060"
                    visible: index + 1 < configItems.length
                }

                Text {
                    id: infoListTitle
                    anchors.verticalCenter: parent.verticalCenter
                    color: Colors.gray_200
                    font: Fonts.body_30
                    text: qsTr(modelData.title)
                }

                Text {
                    id: valueText
                    width: Math.min((parent.width - infoListTitle.contentWidth - (menuImage.visible ? menuImage.width : 0) - 22), implicitWidth)
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: menuImage.visible ? menuImage.left : parent.right
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                    color: Colors.gray_400
                    font: Fonts.body_26
                    text: modelData.value
                }

                Image {
                    id: menuImage
                    width: height
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    fillMode: Image.Pad
                    horizontalAlignment: Qt.AlignRight
                    visible: modelData.onClicked !== undefined
                    source: "../../icon/right.svg"
                }

                Rectangle { // dot
                    width: 16
                    height: width
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: valueText.left
                    anchors.rightMargin: 6
                    radius: width / 2
                    color: modelData.warning ? "red" : Colors.brand
                    visible: modelData.dot
                }
            }

            signal clicked();

            TapHandler {
                onTapped: {
                    clicked()
                    if (modelData.onClicked !== undefined)
                        modelData.onClicked()
                }
            }

            StateColorHandler {
                id: backColor
                stateColor: StateColors.get("transparent_pressed")
            }
        }
    }

}