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
    property var drives: []
    property var selectedDriveIndex: 0
    property var rootPath: drives.length > 0 ? drives[selectedDriveIndex] : ""
    property var currentPath: rootPath
    property var entries: []
    property var selectedEntry: null
    property var copyStatus: ""
    property var formatState: "idle"  // idle, confirm, formatting, done, failed

    Timer {
        id: formatResetTimer
        interval: 3000
        repeat: false
        onTriggered: formatState = "idle"
    }

    Timer {
        id: dirRefreshTimer
        interval: 5000
        running: currentPath !== ""
        repeat: true
        onTriggered: refreshEntries()
    }

    function refreshEntries() {
        if (currentPath === "") return;
        try {
            entries = JSON.parse(X1PlusNative.listDir(currentPath)).filter(function(e) {
                return e.name.charAt(0) !== '.' && e.name !== "System Volume Information";
            });
        } catch(e) {
            entries = [];
        }
    }

    function navigateTo(path) {
        currentPath = path;
        selectedEntry = null;
        copyStatus = "";
        try {
            entries = JSON.parse(X1PlusNative.listDir(path)).filter(function(e) {
                return e.name.charAt(0) !== '.' && e.name !== "System Volume Information";
            });
        } catch(e) {
            entries = [];
        }
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
        if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + " MB";
        return (bytes / 1073741824).toFixed(2) + " GB";
    }

    function parentPath(path) {
        var idx = path.lastIndexOf("/");
        return idx > 0 ? path.substring(0, idx) : path;
    }

    property var displayEntries: currentPath !== rootPath
        ? [{name: "..", isDir: true, size: 0, isParent: true}].concat(entries)
        : entries

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "copy"
            title: copyStatus !== "" ? copyStatus : qsTr("Copy to SD card")
            visible: selectedEntry !== null && !selectedEntry.isDir &&
                     selectedEntry.name.slice(-10).toLowerCase() === ".gcode.3mf"
            keepDialog: true
            onClicked: {
                var src = currentPath + "/" + selectedEntry.name;
                X1PlusNative.system("mkdir -p /sdcard/usb_imports");
                var ret = X1PlusNative.system("cp '" + src + "' '/sdcard/usb_imports/'");
                copyStatus = ret === 0 ? qsTr("Copied!") : qsTr("Copy failed");
            }
        }
        DialogButtonItem {
            name: "format"
            title: formatState === "idle"      ? qsTr("Format Drive") :
                   formatState === "confirm"   ? qsTr("⚠ Erase all data?") :
                   formatState === "formatting"? qsTr("Formatting...") :
                   formatState === "done"      ? qsTr("Format complete!") :
                                                 qsTr("Format failed")
            visible: drives.length > 0
            keepDialog: true
            onClicked: {
                if (formatState === "idle") {
                    formatState = "confirm";
                } else if (formatState === "confirm") {
                    var dev = X1PlusNative.popen("awk '$2 == \"" + rootPath + "\" {print $1}' /proc/mounts").trim();
                    if (!dev || dev.length === 0) {
                        formatState = "failed";
                        formatResetTimer.start();
                        return;
                    }
                    formatState = "formatting";
                    X1PlusNative.system("umount '" + rootPath + "'");
                    var ret = X1PlusNative.system("mkfs.vfat -F 32 '" + dev + "'");
                    X1PlusNative.system("mount '" + dev + "' '" + rootPath + "'");
                    if (ret === 0) {
                        currentPath = rootPath;
                        navigateTo(rootPath);
                        formatState = "done";
                    } else {
                        formatState = "failed";
                    }
                    formatResetTimer.start();
                } else if (formatState === "done" || formatState === "failed") {
                    formatResetTimer.stop();
                    formatState = "idle";
                }
            }
        }
        DialogButtonItem {
            name: "close"
            title: qsTr("Close")
            isDefault: true
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

        Row {
            width: parent.width
            height: drives.length > 1 ? 48 : 0
            visible: drives.length > 1
            spacing: 8

            Text {
                anchors.verticalCenter: parent.verticalCenter
                font: Fonts.body_26
                color: Colors.gray_200
                text: qsTr("Drive:")
            }

            Repeater {
                model: drives
                delegate: Rectangle {
                    width: 100
                    height: 36
                    radius: 6
                    anchors.verticalCenter: parent.verticalCenter
                    color: index === selectedDriveIndex ? Colors.brand : Colors.gray_500

                    Text {
                        anchors.centerIn: parent
                        font: Fonts.body_24
                        color: Colors.gray_100
                        text: "USB " + (index + 1)
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            selectedDriveIndex = index;
                            navigateTo(drives[index]);
                        }
                    }
                }
            }
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
            model: displayEntries
            boundsBehavior: Flickable.StopAtBounds

            footer: Rectangle {
                width: fileList.width
                height: displayEntries.length === 0 ? 52 : 0
                visible: displayEntries.length === 0
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
                color: selectedEntry !== null && selectedEntry.name === modelData.name && !modelData.isParent
                    ? Colors.brand
                    : (index % 2 === 0 ? Colors.gray_600 : Colors.gray_500)
                radius: 4

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 10

                    Text {
                        font: Fonts.body_26
                        color: Colors.gray_100
                        opacity: modelData.isDir ? 0.6 : 0
                        text: "▶"
                    }

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
                        visible: !modelData.isDir
                        text: formatSize(modelData.size)
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (modelData.isParent) {
                            navigateTo(parentPath(currentPath));
                        } else if (modelData.isDir) {
                            navigateTo(currentPath + "/" + modelData.name);
                        } else {
                            selectedEntry = (selectedEntry !== null && selectedEntry.name === modelData.name)
                                ? null : modelData;
                            copyStatus = "";
                        }
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        if (drives.length > 0) {
            navigateTo(drives[0]);
        }
    }
}
