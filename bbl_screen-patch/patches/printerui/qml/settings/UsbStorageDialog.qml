import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import X1PlusNative 1.0
import "qrc:/uibase/qml/widgets"
import "../dialog"

Item {
    property alias name: textConfirm.objectName
    property var drives: []
    property var selectedDriveIndex: 0
    property var rootPath: drives.length > 0 ? drives[0] : ""
    property var currentPath: rootPath
    property var entries: []
    property var selectedEntry: null
    property var copyStatus: ""

    function navigateTo(path) {
        currentPath = path;
        selectedEntry = null;
        copyStatus = "";
        try {
            entries = JSON.parse(X1PlusNative.listDir(path));
        } catch(e) {
            entries = [];
        }
        fileList.positionViewAtBeginning();
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

    property var displayEntries: {
        var base = entries || [];
        return currentPath !== rootPath
            ? [{name: "..", isDir: true, size: 0, isParent: true}].concat(base)
            : base;
    }

    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "copy"
            title: copyStatus !== "" ? copyStatus : qsTr("Copy to SD card")
            visible: selectedEntry !== null && !selectedEntry.isDir &&
                     selectedEntry.name.slice(-6).toLowerCase() === ".gcode"
            keepDialog: true
            onClicked: {
                var src = currentPath + "/" + selectedEntry.name;
                X1PlusNative.system("mkdir -p /sdcard/usb_imports");
                var ret = X1PlusNative.system("cp '" + src + "' '/sdcard/usb_imports/'");
                copyStatus = ret === 0 ? qsTr("Copied!") : qsTr("Copy failed");
            }
        }
        DialogButtonItem {
            name: "close"
            title: qsTr("Close")
            isDefault: true
            keepDialog: false
        }
    }
    property bool finished: false

    id: textConfirm
    width: 960
    height: 480

    // Title
    Text {
        id: titleText
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 48
        font: Fonts.body_36
        color: Colors.gray_100
        verticalAlignment: Text.AlignVCenter
        text: qsTr("USB Storage")
    }

    // Drive selector (only when multiple drives)
    RowLayout {
        id: driveSelectorRow
        anchors.top: titleText.bottom
        anchors.topMargin: 6
        anchors.left: parent.left
        anchors.right: parent.right
        height: drives.length > 1 ? 44 : 0
        visible: drives.length > 1

        Text {
            font: Fonts.body_26
            color: Colors.gray_200
            text: qsTr("Drive:")
        }

        Choise {
            Layout.fillWidth: true
            textFont: Fonts.body_26
            listTextFont: Fonts.body_26
            backgroundColor: Colors.gray_600
            model: drives
            currentIndex: selectedDriveIndex
            onCurrentIndexChanged: {
                selectedDriveIndex = currentIndex;
                rootPath = drives[currentIndex];
                navigateTo(rootPath);
            }
        }
    }

    // Current path breadcrumb
    Text {
        id: pathText
        anchors.top: driveSelectorRow.bottom
        anchors.topMargin: 6
        anchors.left: parent.left
        anchors.right: parent.right
        height: 30
        font: Fonts.body_26
        color: Colors.gray_200
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideMiddle
        text: currentPath
    }

    // Separator
    Rectangle {
        id: separator
        anchors.top: pathText.bottom
        anchors.topMargin: 4
        anchors.left: parent.left
        anchors.right: parent.right
        height: 1
        color: "#606060"
    }

    // File list fills remaining space
    Rectangle {
        anchors.top: separator.bottom
        anchors.topMargin: 2
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        color: "transparent"
        clip: true

        Text {
            anchors.centerIn: parent
            visible: displayEntries.length === 0
            font: Fonts.body_26
            color: Colors.gray_200
            text: currentPath !== "" ? qsTr("No files found") : qsTr("No drives available")
        }

        ListView {
            id: fileList
            anchors.fill: parent
            model: displayEntries
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {
                interactive: true
                policy: fileList.contentHeight > fileList.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            }

            delegate: Rectangle {
                width: fileList.width - (fileList.contentHeight > fileList.height ? 16 : 0)
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
                        text: modelData.isDir ? "▶" : " "
                        opacity: modelData.isDir ? 0.6 : 0
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
                            if (selectedEntry !== null && selectedEntry.name === modelData.name) {
                                selectedEntry = null;
                            } else {
                                selectedEntry = modelData;
                                copyStatus = "";
                            }
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
