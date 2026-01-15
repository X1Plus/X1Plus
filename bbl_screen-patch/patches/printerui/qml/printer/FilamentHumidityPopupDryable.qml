import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import QtQuick.Shapes 1.12
import QtQml 2.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import ".."
import "../X1Plus.js" as X1Plus

Rectangle {
    id: popupRoot
    
    property var popupPad: popupRoot.parent.parent.parent.parent
    
    property var ddsSubmitted: false
    property var waitingForAck: ddsSubmitted && !X1Plus.DDS.lastAmsFilamentDrying()
    property var errorCode: X1Plus.DDS.lastAmsFilamentDrying() && ((X1Plus.DDS.lastAmsFilamentDrying().result == "fail") || (X1Plus.DDS.lastAmsFilamentDrying().result == "timeout"))
    
    property var anyTrayIsLoaded: currentFeeder.trays.some((tray) => tray.exist)
    function filamentIsLowTemp(name) {
        return name == "PLA" || name == "TPU" || name == "PVA" || name == "Support For PLA/PETG";
    }
    property var anyTrayIsLowTemp: currentFeeder.trays.some((tray) => tray.exist && filamentIsLowTemp(tray.typeName))
    
    radius: 15
    color: Colors.gray_600
    ZText {
        id: humidityTitle
        anchors.top: parent.top
        anchors.topMargin: 24
        color: Colors.gray_200
        font: Fonts.head_30
        anchors.horizontalCenter: parent.horizontalCenter
        text: amsTypeIsAms2Pro ? qsTr("AMS 2 Pro status") :
              amsTypeIsAms2Ht ? qsTr("AMS HT status") :
              qsTr("AMS environmental status")
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
        id: columnPanel
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
            id: statusBox
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
                    font: Fonts.head_40
                    color: Colors.gray_200
                    text: qsTr("%1 °C").arg(parseFloat(currentFeederDDS.temp).toFixed(1))
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
                    text: qsTr("Humidity")
                }
                
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_40
                    color: Colors.gray_200
                    text: qsTr("%1% RH").arg(parseFloat(currentFeederDDS.humidity_raw).toFixed(0))
                }
            }

            ColumnLayout {
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                Layout.fillWidth: true
                visible: currentFeederDDS.dry_time > 0
                spacing: 10
                
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_24
                    color: Colors.gray_300
                    text: qsTr("Drying time\nremaining")
                }
                
                Text {
                    property var dry_hours: Math.floor(currentFeederDDS.dry_time / 60)
                    property var dry_minutes: (currentFeederDDS.dry_time % 60).toFixed(0)
                    property var dry_minutes_pad: dry_minutes.length == 1 ? ("0" + dry_minutes) : dry_minutes
                
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_40
                    color: Colors.gray_200
                    text: qsTr("%1h%2m").arg(dry_hours).arg(dry_minutes_pad)
                }
            }
            
            ColumnLayout {
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                Layout.fillWidth: true
                visible: currentFeederDDS.dry_time == 0
                spacing: 10
                
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    font: Fonts.head_24
                    color: Colors.gray_300
                    text: amsIsPluggedIn ? qsTr("Powered\nfrom AC") : qsTr("Not plugged in")
                }
                
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                    Layout.preferredHeight: 80
                    Layout.minimumWidth: 80
                    implicitHeight: 80
                    implicitWidth: 60
                    Layout.fillWidth: true
                    color: "transparent"
                    ZImage {
                        width: 60
                        height: 80
                        anchors.centerIn: parent
                        sourceSize.width: 60
                        sourceSize.height: 80
                        source: amsIsPluggedIn ? "../../icon/plug.svg" : "../../icon/plug-red.svg"
                    }
                }
            }
        }

        ZLineSplitter {
            id: splitter
            Layout.fillWidth: true
            padding: 15
            alignment: Qt.AlignTop
            Layout.topMargin: 5
            Layout.bottomMargin: 10
            color: Colors.gray_300
        }
        
        /* Waiting for ack from forward */
        Text {
            Layout.fillWidth: true
            visible: waitingForAck
            horizontalAlignment: Text.AlignHCenter
            color: Colors.gray_300
            font: Fonts.body_30
            wrapMode: Text.WordWrap
            text: qsTr("Waiting for AMS...")
        }

        /* Forward acked, but with error */
        Text {
            Layout.fillWidth: true
            visible: errorCode
            horizontalAlignment: Text.AlignHCenter
            color: "#eb6600"
            font: Fonts.body_30
            wrapMode: Text.WordWrap
            text: X1Plus.DDS.lastAmsFilamentDrying() && (
                      X1Plus.DDS.lastAmsFilamentDrying().result == "fail"
                          ? qsTr("AMS returned failure code %1.  If it doesn't make sense to you, it doesn't make sense to me either.").arg(X1Plus.DDS.lastAmsFilamentDrying().reason || (X1Plus.DDS.lastAmsFilamentDrying().err_code.toString(16)))
                          : qsTr("AMS command timed out -- try again, maybe?")
                  )
        }

        ZButton {
            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
            visible: errorCode
            tapMargin: 10
            implicitHeight: contentLayout.implicitHeight + 30
            width: textContent.implicitWidth + 30
            text: qsTr("Uh, ok, I guess?")
            onClicked: {
                X1Plus.DDS.setLastAmsFilamentDrying(null);
                ddsSubmitted = false;
            }
        }

        
        /* Currently drying: stop drying button */
        ZButton {
            Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
            visible: currentFeederDDS.dry_time > 0 && !waitingForAck && !errorCode
            tapMargin: 10
            implicitHeight: contentLayout.implicitHeight + 30
            width: textContent.implicitWidth + 30
            text: qsTr("Stop drying")
            onClicked: {
                X1Plus.DDS.publish("device/request/print", {
                    "command": "ams_filament_drying",
                    "ams_id": parseInt(currentFeederDDS.id),
                    "mode": 0,
                    "temp": 0,
                    "duration": 0,
                    "humidity": 0,
                    "rotate_tray": false,
                    "sequence_id": "1234",
                });
                X1Plus.DDS.setLastAmsFilamentDrying(null);
                ddsSubmitted = true;
            }
        }

        Text {
            Layout.fillWidth: true
            visible: currentFeederDDS.dry_time > 0 && !waitingForAck && !errorCode
            color: Colors.gray_300
            font: Fonts.body_24
            wrapMode: Text.WordWrap
            text: qsTr("It can take a minute to stop drying and cool down before the AMS becomes ready to print again.")
        }

        /* Not currently drying: start drying UI */
        GridLayout {
            id: startDryingPanel
            visible: currentFeederDDS.dry_time == 0 && !waitingForAck && !errorCode
            columns: 2
            rowSpacing: 20
            columnSpacing: 20

            RowLayout {
                spacing: 10
                id: temperaturePair

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    text: qsTr("Temperature:")
                    font: Fonts.body_30
                    color: Colors.gray_200
                    wrapMode: Text.WordWrap
                }
                
                ZButton {
                    id: temperatureButton
                    Layout.fillWidth: true
                    property var value: "55"
                    property var defValue: 65
                    property var minValue: 25
                    property var maxValue: amsTypeIsAms2Ht ? 85 : 65
                    Binding on value {
                        value: numberPad.number
                        when: numberPad.target == temperatureButton
                    }
                    Layout.alignment: Qt.AlignVCenter
                    tapMargin: 10
                    implicitHeight: 60
                    width: textContent.implicitWidth + 30
                    text: qsTr("%1 °C").arg(value)
                    
                    onClicked: {
                        numberPad.target = temperatureButton;
                        popupPad.xcloseBtn = false;
                    }
                }
            }

            ZCheckBox {
                id: rotateYourOwl
                Layout.fillWidth: true
                checked: !anyTrayIsLoaded
                checkState: anyTrayIsLoaded ? Qt.PartiallyChecked : Qt.Checked
                enabled: !anyTrayIsLoaded
                textColor: StateColors.get("gray_200")
                textWrapMode: Text.WordWrap
                font: Fonts.body_30
                tapMargin: 0
                text: qsTr("Rotate while drying")
            }

            RowLayout {
                spacing: 10
                id: durationPair

                Text {
                    Layout.alignment: Qt.AlignVCenter
                    text: qsTr("Duration:")
                    font: Fonts.body_30
                    color: Colors.gray_200
                    wrapMode: Text.WordWrap
                }
                
                ZButton {
                    property var value: "8"
                    Layout.fillWidth: true
                    property var defValue: 8
                    property var minValue: 1
                    property var maxValue: 20
                    Binding on value {
                        value: numberPad.number
                        when: numberPad.target == durationButton
                    }
                    
                    id: durationButton
                    Layout.alignment: Qt.AlignVCenter
                    tapMargin: 10
                    implicitHeight: 60
                    width: textContent.implicitWidth + 30
                    text: toString(value) == "1" ? qsTr("1 hour") : qsTr("%1 hours").arg(value)

                    onClicked: {
                        numberPad.target = durationButton;
                        popupPad.xcloseBtn = false;
                    }
                }
            }
            
            ZButton {
                Layout.alignment: Qt.AlignVCenter
                Layout.fillWidth: true
                tapMargin: 10
                enabled: amsIsPluggedIn
                implicitHeight: 60
                width: textContent.implicitWidth + 30
                text: qsTr("Start drying")
                onClicked: {
                    function startDrying() {
    	                X1Plus.DDS.publish("device/request/print", {
                            "command": "ams_filament_drying",
                            "ams_id": parseInt(currentFeederDDS.id),
                            "mode": 1,
                            "temp": Number(temperatureButton.value),
                            "duration": Number(durationButton.value),
                            "humidity": 0,
                            "rotate_tray": !!rotateYourOwl.checked,
                            "sequence_id": "1234",
                        });
                        X1Plus.DDS.setLastAmsFilamentDrying(null);
                        ddsSubmitted = true;
                    }
                    
                    if (!anyTrayIsLowTemp) {
                        startDrying();
                    } else {
                        dialogStack.popupDialog(
                            "TextConfirm", {
                                name: "Drying with low temp filament loaded",
                                type: TextConfirm.YES_NO,
                                titles: [qsTr("Yes, leave me alone"), qsTr("No, that sounds scary")],
                                text: qsTr("At least one feeder appears to have a low-temperature filament loaded.  Drying may cause the feeder to gum up.  Really start drying?"),
                                callback: function(index) {
                                    if (index === TextConfirm.CONFIRM) {
                                        startDrying();
                                    }
                                }
                            });
                    }
                }
            }
        }
    }

    NumberPad {
        id: numberPad
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 15
        anchors.rightMargin: 15
        height: columnPanel.y + splitter.y - 10 /* well, if it's stupid and it works, is it stupid...? */
        anchors.topMargin: 15
        focusItem: startDryingPanel
        onFinished: {
            if (cancel) {
                target.value = target.defValue;
            } else {
                if (number == "")
                    target.value = target.defValue;
                if (Number(target.value) < target.minValue)
                    target.value = target.minValue;
                if (Number(target.value) > target.maxValue)
                    target.value = target.maxValue;
            }
            popupPad.xcloseBtn = true;
        }
    }

    /* Shadow the global dialogStack here -- that dialogStack is in use, but
     * the NumberPad uses it to push and pop things.  Ours isn't hidden. */
    StackView {
        id: dialogStack
        anchors.fill: parent
        initialItem: Item { objectName: "initialItem" }
        pushEnter: null
        pushExit: null
        popEnter: null
        popExit: null
        function popupDialog(dialog, args) {
            if (args === undefined) args = {}
            push("../Dialog.qml", {url: "../dialog/" + dialog + ".qml", args: args})
        }
        
    }
    
    // "StackView.pop()" apparently is a no-op not just when depth is 0, BUT
    // WHEN IT IS 1 ALSO.  So you cannot pop() down to the initialItem, you
    // can only clear() down to it.  Fucking QML!
    Component {
        id: dummyStackItem
        Item {
        }
    }
    
    Component.onCompleted: {
        dialogStack.clear(); // in case anything got left over somehow...
        dialogStack.push(dummyStackItem);
    }
}