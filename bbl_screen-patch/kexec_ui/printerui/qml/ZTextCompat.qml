import QtQuick 2.12
import QtQuick.Controls 2.5
import UIBase 1.0

Text {

    property real maxWidth: 0

    font: Fonts.body_24

    Component.onCompleted: {
        if (maxWidth > 0) {
            width = Math.min(implicitWidth, maxWidth)
            fontSizeMode = Text.HorizontalFit
        }
    }
    onMaxWidthChanged: {
        if(maxWidth > 0) {
            width = Math.min(implicitWidth, maxWidth)
            fontSizeMode = Text.HorizontalFit
        }
    }

    onTextChanged: {
        if (maxWidth > 0) {
            width = Math.min(implicitWidth, maxWidth)
        }
    }
}
