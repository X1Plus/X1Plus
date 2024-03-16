import QtQuick 2.12
import QtQuick.Controls 2.12
import UIBase 1.0
import DdsListener 1.0
import X1PlusNative 1.0
import ".."
import "qrc:/uibase/qml/widgets"

ComboBox {

    property string placeHolder: qsTr("Choose")
    property bool readOnly: false
    property var textColor: Colors.gray_100
    property var textFont: Fonts.body_34
    property var listTextFont: Fonts.body_32
    property var backgroundColor: Colors.gray_500
    property var modelWidth: 0
    property var maxWidth: 2000

    id: comboBox
    height: 60
    width: Math.min(maxWidth, modelWidth + 2*leftPadding + 2*rightPadding + contentItem.padding * 2 + 48)
    
    TextMetrics {
        id: textMetrics
        font: textFont
    }
    
    onModelChanged: {
        textMetrics.font = comboBox.font;
        textMetrics.text = placeHolder;
        modelWidth = textMetrics.width;
        for (var i = 0; i < model.length; i++) {
            textMetrics.text = model[i];
            modelWidth = Math.max(modelWidth, textMetrics.width);
        }
    }
    
    background: Rectangle { visible: !readOnly; color: backgroundColor; radius: 18; border.width: 2; border.color: Colors.gray_800 }
    contentItem: ZTextCompat {
        font: textFont
        color: textColor
        padding: 18
        maxWidth: comboBox.width
        verticalAlignment: Text.AlignVCenter
        text: parent.displayText
    }
    popup.font: Fonts.body_34
    popup.background: Rectangle {
        color: Colors.gray_600
        radius: 18
        border.color: Colors.gray_800
        border.width: 2
    }
    popup.contentItem: ListView {
        id: popupList
        implicitHeight: Math.min(model.length, 5.5) * 60
        width: parent.width
        model: comboBox.model
        clip: true
        currentIndex: comboBox.currentIndex
        highlightMoveDuration: 0
        highlight: Item {
            Rectangle {
                y: 2
                x: 2
                height: parent.height - 4
                width: parent.parent.width - 4
                anchors.margins: 9
                color: Colors.gray_500
                radius: 18
            }
        }
        delegate: ZTextCompat {
            height: 60
            width: comboBox.width
            font: listTextFont
            color: Colors.gray_100
            padding: 18
            maxWidth: comboBox.width
            verticalAlignment: Text.AlignVCenter
            text: modelData
            TapHandler {
                gesturePolicy: TapHandler.ReleaseWithinBounds
                onTapped: {
                    comboBox.currentIndex = index
                    comboBox.popup.close()
                }
            }
            HoverHandler {
                onHoveredChanged: {
                    if (hovered)
                        popupList.currentIndex = index
                }
            }
        }

        SimplePager {
            target: popupList
            anchors.right: popupList.right
            anchors.bottom: popupList.bottom
            current: popupList.contentY
            btnType: ZButtonAppearance.Secondary
            onStepTo: popupList.contentY = position
        }

    }
    displayText: currentIndex == -1 ? placeHolder : qsTr(currentText)

    onDownChanged: {
        var rotate = X1PlusNative.getenv("QT_QUICK_ROTATE_SCREEN");
        if (rotate == "") {
            rotate = 0;
        } else {
            rotate = parseInt(rotate);
        }
        popup.background.rotation = rotate
        popup.contentItem.rotation = rotate
        if (rotate === -90 || rotate === 270) {
            popup.x = width / 2 + popup.contentItem.implicitHeight / 2
            popup.y = width / -2 + height + popup.contentItem.implicitHeight / 2
        }
        //popup.contentItem.children[1].visible = false
    }
}
