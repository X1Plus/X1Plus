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
    property var status: X1Plus.Polar.status()
    
    property string last_username: status.username
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
                source: "../../icon/components/cloud.svg"
            }

            Text {
                id: titleName
                anchors.left: brandImage.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                color: Colors.gray_200
                font: Fonts.body_36
                text: qsTr("Polar Cloud connection")
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

        GridLayout {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            // do not specify a bottom anchor, it'll get stretchy otherwise
            anchors.margins: 40
            rowSpacing: 20
            columnSpacing: 12
            columns: 2

            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                text: qsTr("You can connect your X1Plus-powered printer to Polar Cloud for remote monitoring and printing.  For more information, visit the Polar Cloud web site: <b><u><font color='#6688FF'>https://www.polar3d.com/</font></u></b>.")
                font: Fonts.body_32
                color: Colors.gray_200
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                height: 1
                color: Colors.gray_500
            }

            // Enable switch
            Text {
                Layout.fillWidth: true
                text: status.enabled ? qsTr("Polar Cloud connection is enabled.")
                                     : qsTr("Polar Cloud connection is disabled.")
                font: Fonts.body_28
                color: Colors.gray_200
            }

            ZSwitchButton {
                id: cloudSwitch
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                dynamicChecked: status.enabled
                onToggled: {
                    X1Plus.Settings.put("polar.enabled", checked)
                }
            }
            
            Text {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.topMargin: -10
                font: Fonts.body_24
                text: qsTr("RTSP is disabled, but it is required for Polar Cloud to access the chamber camera.  Enable RTSP (LAN-only Live View) from the <b>LAN Access</b> menu if you wish to view chamber camera images from Polar Cloud.")
                color: "#FF6B6B"
                wrapMode: Text.WordWrap
                visible: status.enabled && !RecordManager.rtspServerOn
            }

            Rectangle {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                height: 1
                color: Colors.gray_500
            }

            // Connection status
            Text {
                Layout.fillWidth: true
                text: qsTr("Connection status")
                font: Fonts.body_28
                color: Colors.gray_200
            }

            Text {
                Layout.alignment: Qt.AlignRight
                text: status.connect_state === "ESTABLISHED" ? qsTr("Connected") :
                      status.connect_state === "DISCONNECTED" ? qsTr("Disconnected") :
                      status.connect_state === "WAITING_HELLO" ? qsTr("Authenticating") :
                      status.connect_state === "CONNECTING" ? qsTr("Connecting") :
                      status.connect_state
                font: Fonts.body_28
                color: status.connect_state === "ESTABLISHED" ? Colors.brand : 
                       status.connect_state === "DISCONNECTED" ? "#FF6B6B" : 
                       "#FFFF5C"
            }

            // Connection status
            Text {
                Layout.fillWidth: true
                visible: !!status.last_connection_error
                text: qsTr("Last connection error")
                font: Fonts.body_28
                color: Colors.gray_200
            }

            Text {
                Layout.alignment: Qt.AlignRight
                visible: !!status.last_connection_error
                text: status.last_connection_error
                font: Fonts.body_28
                color: "#FF6B6B"
            }

            Rectangle {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                height: 1
                color: Colors.gray_500
            }

            // Log in / log out buttons
            Text {
                Layout.fillWidth: true
                visible: status.logged_in
                text: qsTr("Logged in as %1").arg(status.username)
                font: Fonts.body_28
                color: Colors.gray_200
            }

            ZButton {
                visible: status.logged_in
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                paddingX: 20
                paddingY: 10
                text: qsTr("Log out")
                onClicked: {
                    X1Plus.Polar.logout()
                }
            }

            Text {
                Layout.fillWidth: true
                visible: !status.logged_in
                text: qsTr("Not authenticated to Polar Cloud")
                font: Fonts.body_28
                color: Colors.gray_200
            }

            ZButton {
                visible: !status.logged_in
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                paddingX: 20
                paddingY: 10
                text: qsTr("Log in")
                onClicked: {
                    showCredentialsDialog = true
                    usernameInput.forceActiveFocus()
                }
            }

            // Polar serial number (if available)
            Text {
                Layout.fillWidth: true
                visible: !!status.serial_number
                text: qsTr("Polar Cloud serial number")
                font: Fonts.body_28
                color: Colors.gray_200
            }

            Text {
                Layout.alignment: Qt.AlignRight
                visible: !!status.serial_number
                text: status.serial_number
                font: Fonts.body_28
                color: Colors.gray_300
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
            width: 1000
            height: 315
            y: 5
            anchors.horizontalCenter: parent.horizontalCenter
            radius: 15
            color: Colors.gray_500

            MouseArea {
                anchors.fill: parent
                onPressed: {
                    mouse.accepted = true
                }
            }

            GridLayout {
                anchors.fill: parent
                anchors.margins: 40
                anchors.bottomMargin: 60
                rowSpacing: 12
                columnSpacing: 20
                columns: 2

                Text {
                    Layout.columnSpan: 2
                    text: qsTr("Log in to Polar Cloud")
                    font: Fonts.body_32
                    color: Colors.gray_100
                    Layout.alignment: Qt.AlignHCenter
                }
                
                Text {
                    text: qsTr("E-mail address")
                    font: Fonts.body_28
                    color: Colors.gray_200
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 60
                    color: Colors.gray_600
                    radius: 10

                    TextInput {
                        id: usernameInput
                        anchors.fill: parent
                        anchors.margins: 15
                        text: status.username || last_username
                        font: Fonts.body_28
                        color: Colors.gray_100
                        verticalAlignment: TextInput.AlignVCenter
                        selectByMouse: true
                        inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoPredictiveText
                    }
                }

                Text {
                    text: qsTr("PIN")
                    font: Fonts.body_28
                    color: Colors.gray_200
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 60
                    color: Colors.gray_600
                    radius: 10

                    TextInput {
                        id: pinInput
                        anchors.fill: parent
                        anchors.margins: 15
                        text: ""
                        font: Fonts.body_28
                        color: Colors.gray_100
                        verticalAlignment: TextInput.AlignVCenter
                        selectByMouse: true
                        inputMethodHints: Qt.ImhDigitsOnly | Qt.ImhNoPredictiveText
                    }
                }

                // Buttons
                RowLayout {
                    Layout.columnSpan: 2
                    spacing: 40
                    Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter

                    ZButton {
                        checked: true
                        paddingY: 12
                        paddingX: 18
                        text: qsTr("Log in")
                        onClicked: {
                            last_username = usernameInput.text
                            X1Plus.Polar.login(usernameInput.text, pinInput.text)
                            pinInput.text = ""
                            showCredentialsDialog = false
                            usernameInput.focus = false
                            pinInput.focus = false
                        }
                    }

                    ZButton {
                        text: qsTr("Cancel")
                        paddingY: 12
                        paddingX: 18
                        onClicked: {
                            showCredentialsDialog = false
                            usernameInput.focus = false
                            pinInput.text = ""
                            pinInput.focus = false
                        }
                    }
                }
            }
        }
    }
}