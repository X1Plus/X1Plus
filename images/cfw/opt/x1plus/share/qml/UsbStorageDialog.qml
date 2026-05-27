import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import "qrc:/uibase/qml/widgets"
import "qrc:/printerui/qml/dialog"
import "qrc:/printerui/qml/X1Plus.js" as X1Plus

Item {
    property alias name: textConfirm.objectName
    property var driveInfo: []
    property int selectedDriveIndex: 0
    property var currentPath: driveInfo.length > selectedDriveIndex ? driveInfo[selectedDriveIndex].path : ""
    property var entries: []
    property var selectedEntry: null
    property var copyStatus: ""

    onSelectedDriveIndexChanged: {
        selectedEntry = null;
        copyStatus = "";
        refreshEntries();
    }

    function refreshEntries() {
        try {
            var all = JSON.parse(X1PlusNative.listDir(currentPath));
            entries = all.filter(function(e) {
                if (e.name.charAt(0) === '.') return false;
                return e.name.toLowerCase().endsWith(".gcode.3mf");
            });
        } catch(e) {
            entries = [];
        }
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: {
            driveInfo = X1Plus.usbDriveInfo();
            refreshEntries();
        }
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
        if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + " MB";
        return (bytes / 1073741824).toFixed(2) + " GB";
    }

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            id: copyButton
            name: "copy"
            title: copyStatus !== "" ? copyStatus : qsTr("Copy to SD card")
            visible: selectedEntry !== null &&
                     selectedEntry.name.toLowerCase().endsWith(".gcode.3mf")
            isDefault: true
            keepDialog: true
            onClicked: {
                var data = X1PlusNative.readFile(currentPath + "/" + selectedEntry.name);
                if (data.length === 0) {
                    copyStatus = qsTr("Copy failed");
                } else {
                    X1PlusNative.saveFile("/sdcard/" + selectedEntry.name, data);
                    copyStatus = qsTr("Copied!");
                }
            }
        }
        DialogButtonItem {
            name: "close"
            title: qsTr("Close")
            isDefault: !copyButton.visible
            keepDialog: false
            onClicked: {}
        }
    }
    property bool finished: false

    id: textConfirm
    width: 960
    height: mainColumn.height

    Column {
        id: mainColumn
        width: 960
        spacing: 0

        Text {
            width: parent.width
            height: 52
            verticalAlignment: Text.AlignVCenter
            font: Fonts.body_36
            color: Colors.gray_100
            text: qsTr("USB Storage")
        }

        Text {
            width: parent.width
            height: 32
            verticalAlignment: Text.AlignVCenter
            font: Fonts.body_26
            color: Colors.gray_200
            elide: Text.ElideMiddle
            text: currentPath !== "" ? currentPath : qsTr("No drives available")
        }

        Item {
            visible: driveInfo.length > 1
            width: parent.width
            height: driveInfo.length > 1 ? 48 : 0

            Row {
                anchors.fill: parent
                anchors.topMargin: 8
                spacing: 8

                Repeater {
                    model: driveInfo.length
                    Rectangle {
                        width: (parent.width - (driveInfo.length - 1) * 8) / driveInfo.length
                        height: parent.height
                        radius: 6
                        color: index === selectedDriveIndex ? Colors.brand : Colors.gray_600

                        Text {
                            anchors.centerIn: parent
                            font: Fonts.body_26
                            color: Colors.gray_100
                            text: driveInfo[index].port
                                ? qsTr("Port %1").arg(driveInfo[index].port.toUpperCase())
                                : qsTr("USB %1").arg(index + 1)
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: selectedDriveIndex = index
                        }
                    }
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#606060"
        }

        ListView {
            id: fileList
            width: parent.width
            height: 320
            clip: true
            model: entries
            boundsBehavior: Flickable.StopAtBounds

            footer: Rectangle {
                width: fileList.width
                height: entries.length === 0 ? 52 : 0
                visible: entries.length === 0
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    font: Fonts.body_26
                    color: Colors.gray_200
                    text: currentPath !== "" ? qsTr("No files found") : qsTr("No drives available")
                }
            }

            delegate: Rectangle {
                width: fileList.width
                height: 52
                color: selectedEntry !== null && selectedEntry.name === modelData.name
                    ? Colors.brand
                    : (index % 2 === 0 ? Colors.gray_600 : Colors.gray_500)
                radius: 4

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 10

                    Text {
                        Layout.fillWidth: true
                        font: Fonts.body_26
                        color: Colors.gray_100
                        elide: Text.ElideRight
                        text: modelData.name
                    }

                    Text {
                        font: Fonts.body_26
                        color: Colors.gray_200
                        text: formatSize(modelData.size)
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        selectedEntry = (selectedEntry !== null && selectedEntry.name === modelData.name)
                            ? null : modelData;
                        copyStatus = "";
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        if (currentPath !== "") refreshEntries();
    }
}
