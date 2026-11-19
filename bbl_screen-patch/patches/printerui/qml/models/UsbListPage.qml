import QtQuick 2.12
import QtQuick.Controls 2.5
import UIBase 1.0
import Printer 1.0

import ".."
import "qrc:/uibase/qml/widgets"

Item {
    property var drives: []
    property string rootPath: ""
    property string currentPath: ""
    property var entries: []
    property var getMeta: null

    signal navigateTo(string path)
    signal rootSelected(string path)
    signal fileSelected(string path)

    Text {
        anchors.centerIn: parent
        visible: drives.length === 0
        font: Fonts.body_38
        color: Colors.gray_500
        text: qsTr("No USB drives connected")
    }

    Row {
        id: driveSelectorRow
        visible: drives.length > 1
        anchors.top: parent.top
        anchors.left: parent.left
        height: drives.length > 1 ? 72 : 0
        spacing: 6

        Repeater {
            model: drives
            delegate: ZButton {
                width: 200
                height: 72
                verticalTapMargin: 4
                text: modelData.usb_port
                    ? qsTr("USB %1").arg(modelData.usb_port.toUpperCase())
                    : qsTr("USB %1").arg(["A","B","C","D"][index] || (index + 1))
                checked: rootPath === modelData.mount_point
                onClicked: rootSelected(modelData.mount_point)
            }
        }
    }

    Text {
        id: pathText
        visible: drives.length > 0 && currentPath !== rootPath
        anchors.top: driveSelectorRow.bottom
        anchors.topMargin: 4
        anchors.left: parent.left
        anchors.right: parent.right
        height: visible ? 28 : 0
        verticalAlignment: Text.AlignVCenter
        font: Fonts.body_24
        color: Colors.gray_400
        elide: Text.ElideLeft
        text: currentPath.substring(rootPath.length)
    }

    Text {
        anchors.centerIn: fileGrid
        visible: drives.length > 0 && fileGrid.model.length === 0
        font: Fonts.body_38
        color: Colors.gray_500
        text: qsTr("No files found")
        z: 1
    }

    GridView {
        id: fileGrid
        visible: drives.length > 0
        anchors.top: pathText.bottom
        anchors.topMargin: 4
        anchors.bottom: parent.bottom
        width: cellWidth * 4
        anchors.horizontalCenter: parent.horizontalCenter
        cellWidth: 251 + 15
        cellHeight: 266 + 14
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        snapMode: GridView.SnapToRow
        highlightFollowsCurrentItem: false

        model: currentPath !== rootPath
            ? [{name: "..", isDir: true, size: 0, isParent: true}].concat(entries)
            : entries

        delegate: Item {
            width: 252
            height: 266

            property string entryFullPath: currentPath + "/" + modelData.name
            property var meta: (!modelData.isDir && !modelData.isParent && getMeta !== null)
                ? getMeta(entryFullPath) : null

            Rectangle {
                id: imgPanel
                width: 252
                height: 188
                radius: 15
                color: Colors.gray_500
                clip: true

                Image {
                    anchors.fill: parent
                    visible: meta !== null && meta.thumbnail && meta.thumbnail.length > 0
                    source: (meta !== null && meta.thumbnail && meta.thumbnail.length > 0)
                        ? "data:image/png;base64," + meta.thumbnail : ""
                    fillMode: Image.PreserveAspectCrop
                    cache: false
                }

                Text {
                    anchors.centerIn: parent
                    visible: modelData.isDir
                    font.pixelSize: 72
                    color: Colors.gray_300
                    text: modelData.isParent ? "↑" : "▶"
                }

                Text {
                    anchors.centerIn: parent
                    visible: !modelData.isDir && !modelData.isParent &&
                             (meta === null || !meta.thumbnail || meta.thumbnail.length === 0)
                    font.pixelSize: 48
                    color: Colors.gray_400
                    text: "≡"
                }
            }

            MarginPanel {
                width: parent.width
                anchors.top: imgPanel.bottom
                anchors.bottom: parent.bottom
                radius: 15
                topRadiusOff: true
                color: Colors.gray_600

                Text {
                    id: entryTitle
                    anchors.left: parent.left
                    anchors.leftMargin: 15
                    anchors.right: parent.right
                    anchors.rightMargin: 15
                    anchors.top: parent.top
                    anchors.topMargin: 8
                    maximumLineCount: 1
                    font: Fonts.body_24
                    color: Colors.gray_200
                    text: modelData.name
                    clip: true
                }

                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: 15
                    anchors.top: entryTitle.bottom
                    anchors.topMargin: 6
                    height: 22
                    spacing: 10
                    visible: meta !== null && (meta.timeEstimate > 0 || meta.weightEstimate > 0)
                    Repeater {
                        model: {
                            var items = [];
                            if (meta && meta.timeEstimate > 0)
                                items.push({ key: "time",   value: Printer.durationString(meta.timeEstimate) });
                            if (meta && meta.weightEstimate > 0)
                                items.push({ key: "weight", value: meta.weightEstimate.toFixed(1) + "g" });
                            return items;
                        }
                        delegate: Row {
                            spacing: 4
                            Image {
                                width: 16; height: 16
                                anchors.verticalCenter: parent.verticalCenter
                                source: "../../icon/" + modelData.key + ".svg"
                                cache: false
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                font: Fonts.body_20
                                color: Colors.gray_200
                                text: modelData.value
                            }
                        }
                    }
                }
            }

            TapHandler {
                onTapped: {
                    if (modelData.isParent) {
                        var idx = currentPath.lastIndexOf("/");
                        navigateTo(idx > 0 ? currentPath.substring(0, idx) : currentPath);
                    } else if (modelData.isDir) {
                        navigateTo(currentPath + "/" + modelData.name);
                    } else {
                        fileSelected(currentPath + "/" + modelData.name);
                    }
                }
            }
        }
    }

    SimplePager {
        anchors.right: fileGrid.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 60
        visible: drives.length > 0
        target: fileGrid
        pageSize: fileGrid.cellHeight * 2
        onStepTo: fileGrid.contentY = position
    }
}
