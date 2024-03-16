import QtQuick 2.0
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"

Item {

    property alias name: textConfirm.objectName
    property string title
    property alias text: textContent.text
    property alias textFont: textContent.font
    property alias checkBoxText: checkBox.text
    property var saveKey: ""
    property int type: TextConfirm.YES_NO
    property var titles: [
        [ qsTr("Confirm") ],
        [ qsTr("Yes"), qsTr("No") ],
        [ qsTr("Yes"), qsTr("No"), qsTr("Cancel") ],
        [ qsTr("Confirm"), "", qsTr("Cancel") ]
    ][type]
    property int defaultButton: 0
    property var callback: function(index) {}
    property var onConfirm: function() { onYes() }
    property var onYes: function() { callback(0) }
    property var onNo: function() { callback(1) }
    property var onCancel: function() { callback(2) }
    property var buttons: SimpleItemModel {
        DialogButtonItem {
            name: "yes_confirm"; title: titles[0]
            isDefault: defaultButton == 0
            onClicked: onConfirm()
        }
        DialogButtonItem {
            name: "no"; title: titles.length > 1 ? titles[1] : ""
            visible: type == TextConfirm.YES_NO || type == TextConfirm.YES_NO_CANCEL
            isDefault: defaultButton == 1
            onClicked: onNo()
        }
        DialogButtonItem {
            name: "cancel"; title: titles.length > 2 ? titles[2] : ""
            visible: type == TextConfirm.YES_NO_CANCEL || type == TextConfirm.CONFIRM_CANCEL
            isDefault: defaultButton == 2
            onClicked: onCancel()
        }
    }
    property bool finished: false

    function buttonClicked(index) {
        if (callback)
            callback(index)
    }

    id: textConfirm
    width: Math.min(1000, textMetrics.implicitWidth)
    height: textContent.contentHeight + (checkBox.visible ? checkBox.height : 0)

    Text { // TextMetrics has BUG
        id: textMetrics
        visible: false
        font: textContent.font
        text: textContent.text
    }

    Text {
        id: textContent
        width: parent.width
        font: Fonts.body_30
        color: Colors.gray_100
        wrapMode: Text.Wrap
    }

    ZCheckBox {
        id: checkBox
        width: parent.width
        visible: (checkBoxText != "")
        anchors.top: textContent.bottom
        anchors.topMargin: 10
        checked: (checkBoxText != "") ? DeviceManager.getSetting(saveKey, false) : false
        textColor: StateColors.get("gray_100")
        textWrapMode: Text.WordWrap
        font: Fonts.body_30
        tapMargin: 0
        onToggled: {
            DeviceManager.putSetting(saveKey, checked)
        }
    }
}
