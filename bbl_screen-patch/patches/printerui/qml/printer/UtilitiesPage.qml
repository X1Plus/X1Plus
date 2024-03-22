import QtQml 2.12
import QtQuick 2.0
import QtQuick.Controls 2.12
import UIBase 1.0
import Printer 1.0

import ".."
import "qrc:/uibase/qml/widgets"

Item {
    id: utilities

    property var selfTestBtnModel: QtObject {
        property string btnText: qsTr("Device self-test");
        property string description: qsTr("Series of inspection actions: calibration, leveling...")
        function onClickedFun() { pageStack.push("SelfTestPage.qml") } }

    property var calibrateBtnModel: QtObject {
        property string btnText: qsTr("Calibrate");
        property string description: qsTr("Ensure the printer be precisely configured in several aspects")
        function onClickedFun() { pageStack.push("CalibrationPage.qml") } }

    property var dryFilamentBtnModel: QtObject {
        property string btnText: qsTr("Dry Filament");
        property string description: qsTr("Control the humidity of filament to improve print quality")
        function onClickedFun() { pageStack.push("DryFilamentPage.qml") } }

    property var utilitiesBtnModel: DeviceManager.hasDryFunction ? // decide the Dry Filament btn visible
        [ selfTestBtnModel, calibrateBtnModel, dryFilamentBtnModel] :
        [ selfTestBtnModel, calibrateBtnModel ]

    Rectangle {
        anchors.fill: parent
        color: Colors.gray_700
        GridView {
            id: utilitiesBtnGridView
            anchors.left: parent.left
            anchors.leftMargin: 20
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            cellWidth: 550
            cellHeight: 270
            interactive: false
            model: utilitiesBtnModel
            delegate: utilitiesBtnComp
        }
    }

    Component {
        id: utilitiesBtnComp
        Item {
            width: 525
            height: 250
            ZButton {
                anchors.fill: parent
                type: ZButtonAppearance.Tertiary

                EventTrack.itemName: "util_" + index

                onClicked: {
                    modelData.onClickedFun()
                }
                ZText {
                    id: utilitiesBtnText
                    anchors.top: parent.top
                    anchors.topMargin: 50
                    anchors.left: parent.left
                    anchors.leftMargin: 40
                    color: Colors.gray_100
                    font: Fonts.body_40
                    maxWidth: 425
                    text: modelData.btnText
                }

                Image {
                    anchors.left: utilitiesBtnText.right
                    anchors.leftMargin: 10
                    anchors.top: utilitiesBtnText.top
                    anchors.topMargin: 3
                    rotation: 180
                    source: "../../icon/return.svg"
                }

                ZText {
                    anchors.top: utilitiesBtnText.bottom
                    anchors.topMargin: 12
                    anchors.bottom: parent.bottom
                    anchors.left: utilitiesBtnText.left
                    anchors.right: parent.right
                    anchors.rightMargin: 30
                    text: modelData.description
                    color: Colors.gray_300
                    font: Fonts.body_26
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
