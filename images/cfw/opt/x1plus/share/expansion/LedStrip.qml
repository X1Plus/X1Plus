import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import "qrc:/printerui/qml/X1Plus.js" as X1Plus

ColumnLayout {
    spacing: 24
    Layout.alignment: Qt.AlignLeft | Qt.AlignTop

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        Text {
            font: Fonts.body_26
            color: Colors.gray_200
            wrapMode: Text.Wrap
            text: qsTr("<b>Number of LEDs:</b>")
        }
        
        ZButton {
            Layout.fillHeight: true
            Layout.preferredWidth: 60
            textColor: StateColors.get("white_900")
            textSize: 32
            text: "-"
            radius: 5
            onClicked: {
                if (config.ledstrip.leds && config.ledstrip.leds > 0) {
                    config.ledstrip.leds--;
                    config = config;
                    changes_pending = true;
                }
            }
        }
        
        Text {
            Layout.fillHeight: true
            Layout.preferredWidth: 40
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            id: leds_text
            font: Fonts.body_26
            color: Colors.gray_200
            text: config.ledstrip.leds || 0
        }
        
        ZButton {
            Layout.fillHeight: true
            Layout.preferredWidth: 60
            textColor: StateColors.get("white_900")
            textSize: 32
            text: "+"
            radius: 5
            onClicked: {
                config.ledstrip.leds = (config.ledstrip.leds || 0) + 1;
                config = config;
                changes_pending = true;
            }
        }
        
        Item {
            Layout.fillWidth: true
            height: 1
        }
    }

    LedConfig {
        Layout.fillWidth: true
    }

    Text {
        visible: changes_pending
        
        font: Fonts.body_28
        Layout.alignment: Qt.AlignCenter
        color: Colors.warning
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.bottomMargin: 18

        text: qsTr("<b>Unsaved changes have been made.</b>")
    }
}
