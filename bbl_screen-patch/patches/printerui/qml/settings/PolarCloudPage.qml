import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import QtQuick.Layouts 1.12
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import ".."  // For X1PBackButton
import '../X1Plus.js' as X1Plus

Item {
    id: polarCloudPage
    property string username: X1Plus.Settings.get("polar.username", "")
    property string pin: X1Plus.Settings.get("polar.pin", "")
    property bool cloudEnabled: X1Plus.Settings.get("polar.enabled", false)
    property string connectionStatus: X1Plus.Settings.get("polar.connection_status", "Not connected")
    property string polarSerial: X1Plus.Settings.get("polar.serial_number", "")
    property string lastError: X1Plus.Settings.get("polar.last_error", "")
    property bool showCredentialsDialog: false

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
                source: "../../../icon/components/cloud.svg"
            }

            Text {
                id: titleName
                anchors.left: brandImage.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                color: Colors.gray_200
                font: Fonts.body_36
                text: qsTr("Polar Cloud Connection")
            }

            ZButton {
                id: returnBtn
                anchors.right: parent.right
                anchors.rightMargin: 28
                anchors.top: parent.top
                anchors.topMargin: 6
                text: qsTr("Return")
                onClicked: { pageStack.pop() }
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
        id: mainPanel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        leftMargin: 16
        rightMargin: 16
        bottomMargin: 16
        radius: 15
        color: Colors.gray_600

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 40
            spacing: 30

            Text {
                text: qsTr("Connect your printer to Polar Cloud for remote monitoring and printing.")
                font: Fonts.body_28
                color: Colors.gray_200
                wrapMode: Text.WordWrap
                width: parent.width
            }

            // Connection status
            Item {
                width: parent.width
                height: 60

                Text {
                    text: qsTr("Connection Status")
                    font: Fonts.body_28
                    color: Colors.gray_200
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 250
                }

                Text {
                    text: polarCloudPage.connectionStatus
                    font: Fonts.body_28
                    color: polarCloudPage.connectionStatus === "Connected" ? Colors.green : 
                           polarCloudPage.connectionStatus === "Connecting..." ? Colors.yellow :
                           polarCloudPage.connectionStatus.indexOf("Error") >= 0 ? "#FF6B6B" : Colors.gray_300
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignRight
                }
            }

            // Polar serial number (if available)
            Item {
                width: parent.width
                height: polarCloudPage.polarSerial ? 60 : 0
                visible: polarCloudPage.polarSerial

                Text {
                    text: qsTr("Polar Cloud Serial")
                    font: Fonts.body_28
                    color: Colors.gray_200
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 250
                }

                Text {
                    text: polarCloudPage.polarSerial
                    font: Fonts.body_28
                    color: Colors.gray_300
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Error display (if any)
            Item {
                width: parent.width
                height: polarCloudPage.lastError ? 80 : 0
                visible: polarCloudPage.lastError

                Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 10

                    Text {
                        text: qsTr("Last Error:")
                        font: Fonts.body_28
                        color: Colors.gray_200
                    }

                    Text {
                        text: polarCloudPage.lastError
                        font: Fonts.body_24
                        color: "#FF6B6B"
                        wrapMode: Text.WordWrap
                        width: parent.width
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: Colors.gray_500
            }

            // Credentials button
            Item {
                width: parent.width
                height: 60

                Text {
                    text: qsTr("Credentials")
                    font: Fonts.body_28
                    color: Colors.gray_200
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                }

                ZButton {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: (polarCloudPage.username && polarCloudPage.pin) ? qsTr("Edit") : qsTr("Set")
                    onClicked: {
                        showCredentialsDialog = true
                    }
                }
            }

            // Current credentials display (masked)
            Item {
                width: parent.width
                height: (polarCloudPage.username || polarCloudPage.pin) ? 80 : 0
                visible: polarCloudPage.username || polarCloudPage.pin

                Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 5

                    Text {
                        text: qsTr("Username: ") + (polarCloudPage.username ? polarCloudPage.username : qsTr("(not set)"))
                        font: Fonts.body_24
                        color: Colors.gray_300
                    }

                    Text {
                        text: qsTr("PIN: ") + (polarCloudPage.pin ? "****" : qsTr("(not set)"))
                        font: Fonts.body_24
                        color: Colors.gray_300
                    }
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: Colors.gray_500
            }

            // Enable switch
            Item {
                width: parent.width
                height: 60

                Text {
                    text: qsTr("Enable Polar Cloud Connection")
                    font: Fonts.body_28
                    color: Colors.gray_200
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                }

                ZSwitchButton {
                    id: cloudSwitch
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    dynamicChecked: polarCloudPage.cloudEnabled
                    enabled: polarCloudPage.username && polarCloudPage.pin
                    onToggled: {
                        polarCloudPage.cloudEnabled = checked
                        X1Plus.Settings.put("polar.enabled", checked)
                    }
                }
            }

            Text {
                text: qsTr("Note: Username and PIN must be set before enabling the connection.")
                font: Fonts.body_24
                color: Colors.gray_400
                wrapMode: Text.WordWrap
                width: parent.width
                visible: !polarCloudPage.username || !polarCloudPage.pin
            }
        }
    }

    // Credentials input dialog
    Item {
        id: credentialsDialog
        anchors.fill: parent
        visible: showCredentialsDialog
        z: 100

        MouseArea {
            anchors.fill: parent
            onPressed: {
                mouse.accepted = true
            }
            onReleased: {
                showCredentialsDialog = false
                usernameInput.focus = false
                pinInput.focus = false
            }
        }

        Rectangle {
            anchors.fill: parent
            color: "#4D000000"
        }

        Rectangle {
            id: dialogRect
            width: 650
            height: 450
            y: 100
            anchors.horizontalCenter: parent.horizontalCenter
            radius: 15
            color: Colors.gray_500

            MouseArea {
                anchors.fill: parent
                onPressed: {
                    mouse.accepted = true
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 40
                anchors.bottomMargin: 60
                spacing: 20

                Text {
                    text: qsTr("Polar Cloud Credentials")
                    font: Fonts.body_36
                    color: Colors.gray_100
                    Layout.alignment: Qt.AlignHCenter
                }

                // Username field
                Column {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: qsTr("Username (Email)")
                        font: Fonts.body_28
                        color: Colors.gray_200
                    }

                    Rectangle {
                        width: parent.width
                        height: 60
                        color: Colors.gray_600
                        radius: 10

                        TextInput {
                            id: usernameInput
                            anchors.fill: parent
                            anchors.margins: 15
                            text: polarCloudPage.username
                            font: Fonts.body_28
                            color: Colors.gray_100
                            verticalAlignment: TextInput.AlignVCenter
                            selectByMouse: true
                            inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoPredictiveText
                        }
                    }
                }

                // PIN field
                Column {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: qsTr("PIN")
                        font: Fonts.body_28
                        color: Colors.gray_200
                    }

                    Rectangle {
                        width: parent.width
                        height: 60
                        color: Colors.gray_600
                        radius: 10

                        TextInput {
                            id: pinInput
                            anchors.fill: parent
                            anchors.margins: 15
                            text: polarCloudPage.pin
                            font: Fonts.body_28
                            color: Colors.gray_100
                            verticalAlignment: TextInput.AlignVCenter
                            selectByMouse: true
                            inputMethodHints: Qt.ImhDigitsOnly | Qt.ImhNoPredictiveText
                        }
                    }
                }

                Item {
                    Layout.fillHeight: true
                }

                // Buttons
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 20

                    ZButton {
                        Layout.fillWidth: true
                        type: ZButtonAppearance.Secondary
                        text: qsTr("Cancel")
                        onClicked: {
                            showCredentialsDialog = false
                            usernameInput.focus = false
                            pinInput.focus = false
                        }
                    }

                    ZButton {
                        Layout.fillWidth: true
                        text: qsTr("Save")
                        onClicked: {
                            polarCloudPage.username = usernameInput.text
                            polarCloudPage.pin = pinInput.text
                            X1Plus.Settings.put("polar.username", usernameInput.text)
                            X1Plus.Settings.put("polar.pin", pinInput.text)
                            showCredentialsDialog = false
                            usernameInput.focus = false
                            pinInput.focus = false
                        }
                    }
                }
            }
        }
    }
}