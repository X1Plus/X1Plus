import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0

import "qrc:/uibase/qml/widgets"

Item {

    property bool hideOnDisabled: true
    property var target: parent
    property real total: target.contentHeight
    property real current: target.contentY
    property real pageSize: target.height
    property real viewport: target.height
    property var btnType: ZButtonAppearance.Tertiary

    signal stepTo(real position)

    id: pager
    width: 112
    height: 210

//    MouseArea {
//        anchors.fill: parent
//        onPressed: { mouse.accepted = true }
//    }

    ZButton {
        id: upBtn
        height: width
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 12
        type: btnType
        cornerRadius: width / 2
        iconSize: 0
        icon: "../image/up.svg"
        enabled: current > 0
        visible: !hideOnDisabled || enabled
        onClicked: {
            var p = current - pageSize
            p = Math.ceil(p / pageSize) * pageSize
            if (p < 0)
                p = 0
            stepTo(p)
        }
    }

    ZButton {
        id: downBtn
        height: width
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 12
        type: btnType
        cornerRadius: height / 2
        iconSize: 0
        icon: "../image/up.svg"
        rotation: 180
        enabled: current + viewport < total
        visible: !hideOnDisabled || enabled
        onClicked: {
            var p = current + pageSize
            p = Math.floor(p / pageSize) * pageSize
            if (p + viewport > total)
                p = total - viewport
            stepTo(p)
        }
    }
}
