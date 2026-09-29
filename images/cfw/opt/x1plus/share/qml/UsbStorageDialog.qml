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
    property var usb: X1Plus.Expansion.usb()

    property var port: "" /* passed in from above */
    property int selectedDriveIndex: usb.mounts.findIndex(m => m.usb_port == port) /* gets overridden later */
    property var rootPath: (selectedDriveIndex >= 0 && usb.mounts.length > selectedDriveIndex) ? usb.mounts[selectedDriveIndex].mount_point : ""
    property var currentPath: rootPath
    property var entries: []
    property var selectedEntry: null
    property var copyStatus: ""

    /* State of the background copy (see X1PlusNative.startCopy).  The copy
     * lives in the native layer, so it keeps going if this dialog is closed,
     * and we pick it back up if the dialog is reopened. */
    property var copy: ({ state: "idle", done: 0, total: 0 })
    property bool copying: copy.state === "copying"
    property bool watchingCopy: false

    readonly property var printableSuffixes: [".gcode.3mf", ".gcode"]
    readonly property string destDir: "/sdcard"

    function isPrintable(name) {
        var lower = name.toLowerCase();
        return printableSuffixes.some(s => lower.endsWith(s));
    }

    /* path shown to the user: relative to the root of the drive */
    function displayPath() {
        if (rootPath === "")
            return qsTr("No drives available");
        var rel = currentPath.substring(rootPath.length);
        return rel === "" ? "/" : rel;
    }

    onRootPathChanged: {
        currentPath = rootPath;
    }

    onCurrentPathChanged: {
        selectedEntry = null;
        if (!copying) copyStatus = "";
        refreshEntries();
        fileList.positionViewAtBeginning();
    }

    function refreshEntries() {
        if (currentPath === "") {
            entries = [];
            return;
        }

        var all;
        try {
            all = JSON.parse(X1PlusNative.listDir(currentPath));
        } catch(e) {
            all = [];
        }

        var list = all.filter(function(e) {
            if (e.name.charAt(0) === '.') return false;
            return e.isDir || isPrintable(e.name);
        });

        if (currentPath !== rootPath) {
            list.unshift({ name: "..", isDir: true, size: 0, isParent: true });
        }

        /* drop the selection if the file has gone away */
        if (selectedEntry !== null && !list.some(e => !e.isDir && e.name === selectedEntry.name)) {
            selectedEntry = null;
        }

        entries = list;
    }

    function enterEntry(entry) {
        if (entry.isParent) {
            var up = currentPath.substring(0, currentPath.lastIndexOf("/"));
            currentPath = (up.length < rootPath.length) ? rootPath : up;
        } else {
            currentPath = currentPath + "/" + entry.name;
        }
    }

    function pollCopy() {
        try {
            copy = JSON.parse(X1PlusNative.copyStatus());
        } catch(e) {
            copy = { state: "idle", done: 0, total: 0 };
        }

        if (copy.state === "copying") {
            watchingCopy = true;
            var pct = copy.total > 0 ? Math.floor(100 * copy.done / copy.total) : 0;
            copyStatus = qsTr("Copying... %1% (tap to cancel)").arg(pct);
            return;
        }

        if (!watchingCopy)
            return;
        watchingCopy = false;

        if (copy.state === "done") {
            copyStatus = qsTr("Copied to SD card!");
        } else if (copy.state === "cancelled") {
            copyStatus = qsTr("Copy cancelled");
        } else if (copy.state === "error") {
            copyStatus = qsTr("Copy failed");
            console.log("[x1p] USB copy failed: " + copy.error);
        }
    }

    function startCopy() {
        var src = currentPath + "/" + selectedEntry.name;
        var free = X1PlusNative.freeSpace(destDir);
        /* leave a little headroom so we don't fill the card to the brim */
        if (free >= 0 && free < selectedEntry.size + 16 * 1048576) {
            copyStatus = qsTr("Not enough space on SD card");
            return;
        }
        if (X1PlusNative.startCopy(src, destDir + "/" + selectedEntry.name)) {
            watchingCopy = true;
            pollCopy();
        } else {
            copyStatus = qsTr("Copy failed");
        }
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: {
            if (selectedDriveIndex >= usb.mounts.length) {
                selectedDriveIndex = 0;
            }
            refreshEntries();
        }
    }

    Timer {
        /* fast poll only while a copy is running */
        interval: 250
        running: copying
        repeat: true
        onTriggered: pollCopy()
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
            visible: selectedEntry !== null || copying
            isDefault: true
            keepDialog: true
            onClicked: {
                if (copying) {
                    X1PlusNative.cancelCopy();
                    return;
                }
                if (selectedEntry !== null)
                    startCopy();
            }
        }
        DialogButtonItem {
            name: "close"
            title: qsTr("Close")
            isDefault: !copyButton.visible
            keepDialog: false
            onClicked: {} /* an in-progress copy keeps running in the background */
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
            text: displayPath()
        }

        Item {
            visible: usb.mounts.length > 1
            width: parent.width
            height: usb.mounts.length > 1 ? 48 : 0

            Row {
                anchors.fill: parent
                anchors.topMargin: 8
                spacing: 8

                Repeater {
                    model: usb.mounts.length
                    Rectangle {
                        width: (parent.width - (usb.mounts.length - 1) * 8) / usb.mounts.length
                        height: parent.height
                        radius: 6
                        color: index === selectedDriveIndex ? Colors.brand : Colors.gray_600

                        Text {
                            anchors.centerIn: parent
                            font: Fonts.body_26
                            color: Colors.gray_100
                            text: usb.mounts[index].usb_port
                                ? qsTr("Port %1").arg(usb.mounts[index].usb_port.toUpperCase())
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
                height: entries.filter(e => !e.isParent).length === 0 ? 52 : 0
                visible: height > 0
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    font: Fonts.body_26
                    color: Colors.gray_200
                    text: currentPath !== "" ? qsTr("No .gcode.3mf or .gcode files here") : qsTr("No drives available")
                }
            }

            delegate: Rectangle {
                width: fileList.width
                height: 52
                color: (!modelData.isDir && selectedEntry !== null && selectedEntry.name === modelData.name)
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
                        color: modelData.isDir ? Colors.gray_200 : Colors.gray_100
                        elide: Text.ElideRight
                        text: modelData.isParent ? qsTr(".. (up one folder)")
                            : modelData.isDir ? (modelData.name + "/")
                            : modelData.name
                    }

                    Text {
                        font: Fonts.body_26
                        color: Colors.gray_200
                        text: modelData.isDir ? "" : formatSize(modelData.size)
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (modelData.isDir) {
                            enterEntry(modelData);
                            return;
                        }
                        selectedEntry = (selectedEntry !== null && selectedEntry.name === modelData.name)
                            ? null : modelData;
                        if (!copying) copyStatus = "";
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        pollCopy(); /* pick up a copy that is still running from a previous visit */
        if (currentPath !== "") refreshEntries();
    }
}
