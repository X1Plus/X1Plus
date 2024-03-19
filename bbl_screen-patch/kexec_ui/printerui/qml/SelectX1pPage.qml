import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0
import DdsListener 1.0
import X1PlusNative 1.0

import "qrc:/uibase/qml/widgets"

import "settings"
import "."

Rectangle {
    id: screen
    width: 1280
    height: 720
    color: Colors.gray_500
    
    property var noBackButton: false
    
    property var x1pName: null
    property var x1pJson: null
    property var x1pNames: [ ]
    property var x1pJsons: [ ]
    
    Component.onCompleted: {
        var x1ps = X1PlusNative.listX1ps(X1PlusNative.getenv("EMULATION_WORKAROUNDS") + "/sdcard");
        for (var i = 0; i < x1ps.length; i += 2) {
            x1pNames.push(x1ps[i]);
            x1pJsons.push(JSON.parse(x1ps[i+1]));
        }
        x1pNames = x1pNames;
        x1pJsons = x1pJsons;
        console.log(x1pNames, x1pJsons);
    }
    
    Component.onDestruction: {
    }


    Text {
        id: titlelabel
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.topMargin: 48
        anchors.leftMargin: noBackButton ? 48 : 95
        anchors.right: parent.right
        font: Fonts.head_48
        color: Colors.brand
        text: "X1Plus custom firmware installation"
    }

    ZButton {
        visible: !noBackButton
        anchors.verticalCenter: titlelabel.verticalCenter
        anchors.left: body.left
        anchors.leftMargin: -width * 0.38 // fudge it to align with the button
        height: width
        width: 80
        cornerRadius: width / 2
        iconSize: 40
        type: ZButtonAppearance.Secondary
        icon: "../image/return.svg"
        onClicked: {
            dialogStack.replace("BootOptionsPage.qml");
        }
    }

    ZLineSplitter {
        id: splitter
        height: 2
        anchors.top: titlelabel.bottom
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.topMargin: 24
        padding: 15
        color: Colors.gray_300
    }
    
    Item {
        id: body
        anchors.top: splitter.bottom
        anchors.topMargin: 24
        anchors.left: parent.left
        anchors.leftMargin: 48
        anchors.right: parent.right
        anchors.rightMargin: 48
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 48
        
        Text {
            id: chooseText
            anchors.left: parent.left
            anchors.verticalCenter: chooseBox.verticalCenter
            width: implicitWidth
            color: Colors.gray_100
            font: Fonts.body_28
            text: "Select a firmware bundle to install:"
        }
        
        Choise {
            id: chooseBox
            anchors.leftMargin: 16
            anchors.left: chooseText.right
            anchors.top: parent.top
            maxWidth: parent.width - x
            textFont: Fonts.body_28
            listTextFont: Fonts.body_26
            backgroundColor: Colors.gray_500
            model: x1pNames
            onCurrentIndexChanged: {
                x1pName = x1pNames[currentIndex];
                x1pJson = x1pJsons[currentIndex];
                console.log(currentIndex);
            }
            placeHolder: "No .x1p files found on SD card."
        }
        
        Rectangle {
            id: detailBox
            border.color: Colors.gray_300
            border.width: 2
            color: "transparent"
            radius: 16
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: chooseBox.bottom
            anchors.bottom: buttonBox.top
            anchors.topMargin: 16
            anchors.bottomMargin: 24
            clip: true

            ListView {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.top: parent.top
                anchors.topMargin: 16
                anchors.right: parent.right
                anchors.rightMargin: 16
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 16
                boundsBehavior: Flickable.StopAtBounds
                id: details
                model: [true]
                ScrollBar.vertical: ScrollBar {
                    interactive: true
                    policy: details.contentHeight > details.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                }
                interactive: true
                delegate: Text {
                    id: details
                    width: parent.width
                    color: Colors.gray_100
                    font: Fonts.body_28
                    wrapMode: Text.WordWrap
                    text: x1pJson != null
                            ? `<b>Custom firmware version:</b> ${x1pJson.cfwVersion}<br>`+
                              `<b>Bambu Lab base firmware version:</b> ${x1pJson.base.version}<br>`+
                              `<b>Build date:</b> ${x1pJson.date}<br><br>`+
                              `<b>Release notes:</b> ${x1pJson.notes.replace(/\n/g,'<br>')}`
                            : "No custom firmware installation bundles found on SD card.  Copy a <b>.x1p</b> file to the SD card and try again."
                }
            }
        }
        
        Item {
            id: buttonBox
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 64
            
            ZButton {
                id: installBtn
                height: parent.height
                x: (parent.width - width) / 2
                checked: true
                text: `Install ${x1pName ? x1pName : 'custom firmware'}`
                enabled: x1pJson != null
                onClicked: {
                    dialogStack.popupDialog("TextConfirm", {
                        name: "install confirm",
                        text: "Are you sure you're ready to install the X1Plus custom firmware?<br><br>"+
                              "While we've done our best to make X1Plus as safe as possible, there are always risks associated with modifying your printer.  X1Plus comes with NO WARRANTY, EXPRESS OR IMPLIED, and by installing it, you accept that you and you alone are responsible for the risk of damage to your printer, or its surroundings.<br><br>Once the installation process begins, don't touch your printer until it completes.  It could take up to 10 minutes (or longer, depending on Internet connection speed) to install.",
                        titles: ["Yes! Install X1Plus!", "Er, never mind"],
                        onYes: function() { dialogStack.pop(); dialogStack.replace("InstallingPage.qml", { x1pName: x1pName }); },
                        onNo: function() { dialogStack.pop(); },
                    });
                }
            }
        }
    }
}
