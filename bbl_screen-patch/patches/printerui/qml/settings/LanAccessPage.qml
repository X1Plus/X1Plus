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
                source: "../../icon/wiredNetworkIcon.svg"
            }

            Text {
                id: titleName
                anchors.left: brandImage.right
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                color: Colors.gray_200
                font: Fonts.body_36
                text: "LAN access settings"
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
        id: informational_text
        width: 400
        anchors.top: title.bottom
        anchors.left: parent.left
        leftMargin: 16
        height: 295
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
            
            text: qsTr("X1Plus allows you to connect to your printer over your local network, not only using the slicer.  For your security, only enable services that you plan to use.")
        }
    }
    
    
    MarginPanel {
        id: lancode_panel
        width: 400
        anchors.top: informational_text.bottom
        anchors.left: parent.left
        leftMargin: 16
        topMargin: 14
        anchors.bottom: parent.bottom
        bottomMargin: 16
        radius: 15
        color: Colors.gray_600
        
        Text {
            id: lanAccessCodeLabel
            font: Fonts.body_36
            color: Colors.gray_100
            anchors.top: parent.top
            anchors.topMargin: 25
            anchors.left: parent.left
            anchors.right: parent.right
            horizontalAlignment: Text.AlignHCenter
            text: qsTr("LAN access code")
        }
        
        Text {
            id: curToken
            color: "#00AE42"
            font: Fonts.head_48
            anchors.top: lanAccessCodeLabel.bottom
            anchors.topMargin: 25
            anchors.left: parent.left
            anchors.right: parent.right
            horizontalAlignment: Text.AlignHCenter
            text: `<font size=\"4\">${NetworkManager.lanAccessToken || 'a1b2c3d4'}</font>`
        }

        ZButton {
            id: refreshBtn
            width: 46
            height: width
            radius: width / 2
            anchors.top: curToken.bottom
            anchors.topMargin: 20
            anchors.horizontalCenter: lanAccessCodeLabel.horizontalCenter
            type: ZButtonAppearance.Secondary
            iconPosition: ZButtonAppearance.Center
            paddingX: 0
            iconSize: 46
            textColor: StateColors.get("gray_100")
            icon: "../../icon/refresh.svg"
            onClicked: {
                NetworkManager.refreshLanAccessToken()
            }
            RotationAnimation {
                id: rotationId
                target: refreshBtn.iconItem
                property: "rotation"
                loops: Animation.Infinite
                alwaysRunToEnd: true
                duration: 1000
                from: 0
                to: 360
                running: NetworkManager.tokenSyncing
            }
        }

    }

    MarginPanel {
        id: infosPanel
        anchors.left: informational_text.right
        anchors.right: parent.right
        rightMargin: 16
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        bottomMargin: 15
        leftMargin: 16
        radius: 15
        color: Colors.gray_600

        GridLayout {
            rowSpacing: 6
            columnSpacing: 12
            columns: 2
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            anchors.topMargin: 20
            Layout.alignment: Qt.AlignLeft | Qt.AlignTop
            Layout.maximumWidth: 1000

            /*** RTSP ***/

            Text {
                Layout.fillWidth: true
                font: Fonts.body_28
                color: Colors.gray_100
                wrapMode: Text.Wrap
                text: RecordManager.rtspServerOn ? qsTr("RTSP server (LAN-only live view) is enabled.") : qsTr("RTSP server (LAN-only live view) is disabled.")
            }
            
            ZSwitchButton {
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                dynamicChecked: RecordManager.rtspServerOn
                enabled: !RecordManager.syncingRtspServer
                onToggled: {
                    RecordManager.rtspServerOn = checked
                }
            }

            ZLineSplitter {
                Layout.fillWidth: true
                Layout.columnSpan: 2
                Layout.topMargin: 20
                Layout.bottomMargin: 10
                alignment: Qt.AlignTop
                padding: 24
                color: Colors.gray_300
            }

            /*** VNC ***/

            Text {
                Layout.fillWidth: true
                font: Fonts.body_28
                color: Colors.gray_100
                wrapMode: Text.Wrap
                text: X1Plus.Settings.get("vnc.enabled", false) ? qsTr("VNC server (remote desktop) is enabled.") : qsTr("VNC server (remote desktop) is disabled.")
            }
            
            ZSwitchButton {
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                dynamicChecked: !!X1Plus.Settings.get("vnc.enabled", false)
                onToggled: {
                    X1Plus.Settings.put("vnc.enabled", checked)
                }
            }
            
            Text {
                Layout.fillWidth: true
                font: Fonts.body_26
                color: Colors.gray_200
                wrapMode: Text.Wrap
                visible: !!X1Plus.Settings.get("vnc.enabled", false)
                text: X1Plus.Settings.get("vnc.password", null) == null ? qsTr("The VNC password is set to the LAN access code.") :
                      X1Plus.Settings.get("vnc.password", null) == ""   ? qsTr("The VNC password is disabled.  Be careful!") :
                                                                          qsTr("The VNC password has been customized through the X1Plus command-line, and is not shown here.");
            }

            ZLineSplitter {
                Layout.fillWidth: true
                Layout.columnSpan: 2
                Layout.topMargin: 20
                Layout.bottomMargin: 10
                alignment: Qt.AlignTop
                padding: 24
                color: Colors.gray_300
            }
            
            /*** SSH ***/
            
            Text {
                Layout.fillWidth: true
                font: Fonts.body_28
                color: Colors.gray_100
                wrapMode: Text.Wrap
                text: enableSshSw.dynamicChecked ? qsTr("SSH server (remote command line) is enabled.") : qsTr("SSH server (remote command line) is disabled.")
            }
            
            ZSwitchButton {
                id: enableSshSw
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                dynamicChecked: !!X1Plus.Settings.get("ssh.enabled", false)
                onToggled: {
                    X1Plus.Settings.put("ssh.enabled", checked)
                }
            }
            
            Text {
                property var rootpw: X1Plus.Settings.get("ssh.root_password", false)
                function regenRootPw() {
                    var newpw = X1PlusNative.popen(`dd if=/dev/urandom bs=10 count=1 | md5sum | cut -c 1-12`); // now THAT is cheesy!
                    X1Plus.Settings.put("ssh.root_password", newpw);
                }
            
                id: rootpwText
                font: Fonts.body_26
                color: Colors.gray_200
                text: qsTr("Root password: ") + "<font color=\"#00AE42\">" + (rootpw == "" ? qsTr("[not yet set]") : rootpw) + "</font>"
                visible: enableSshSw.dynamicChecked
            }

            ZButton {
                id: refreshRootPwBtn
                width: 46
                height: width
                radius: width / 2
                type: ZButtonAppearance.Secondary
                iconPosition: ZButtonAppearance.Center
                paddingX: 0
                paddingY: 15
                iconSize: 46
                textColor: StateColors.get("gray_100")
                visible: enableSshSw.dynamicChecked
                icon: "../../icon/refresh.svg"
                onClicked: {
                    rootpwText.regenRootPw()
                    rootpwRotationId.start()
                }

                RotationAnimation {
                    id: rootpwRotationId
                    target: refreshRootPwBtn.iconItem
                    property: "rotation"
                    loops: 1
                    alwaysRunToEnd: true
                    duration: 1000
                    from: 0
                    to: 360
                }
            }
        }
    }
}
