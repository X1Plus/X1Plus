import QtQuick 2.12
import UIBase 1.0

ZButton {
    property int topMargin: 26
    property int leftMargin: 16
    anchors.left: parent.left
    anchors.leftMargin: leftMargin
    anchors.top: parent.top
    anchors.topMargin: topMargin 
    height: width
    width: 80
    cornerRadius: width / 2
    iconSize: 40
    type: ZButtonAppearance.Secondary
    icon: "../icon/return.svg"       
}

