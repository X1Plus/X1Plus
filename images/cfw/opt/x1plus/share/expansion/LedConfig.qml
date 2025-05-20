import QtQuick 2.0
import QtQuick.Controls 2.12
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"
import "qrc:/printerui/qml/X1Plus.js" as X1Plus

ColumnLayout {
    spacing: 24
    Layout.alignment: Qt.AlignLeft | Qt.AlignTop

    property var animations_available: [ "running", "paused", "finish", "failed", "rainbow" ]
    property var animations_enabled: config.ledstrip.animations || animations_available

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        Text {
            font: Fonts.body_26
            color: Colors.gray_200
            wrapMode: Text.Wrap
            text: qsTr("<b>Brightness:</b>")
        }
        
        Slider {
            Layout.fillWidth: true
            from: 0
            value: config.ledstrip.brightness || 0.4
            to: 1.0
            onMoved: {
                config.ledstrip.brightness = value;
                config = config;
                changes_pending = true;
            }
            background: Rectangle {
                anchors.centerIn: parent
                width: parent.width-12
                height: 10
                radius: height / 2
                color: Colors.gray_600
                
                Rectangle {
                    width: parent.parent.visualPosition * parent.width
                    height: parent.height
                    radius: height / 2
                    color: Colors.brand
                }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        
        Text {
            font: Fonts.body_26
            color: Colors.gray_200
            wrapMode: Text.Wrap
            text: qsTr("<b>Enabled animations:</b>")
        }
        
        /* This removes a lot of the flexibility of the configuration
         * system, but so be it.  If you made changes by hand, this will
         * probably blow them away.  */
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            orientation: ListView.Horizontal
            model: animations_available
            clip: true
            spacing: 12
            
            delegate: ZButton {
                text: modelData
                height: ListView.view.height - 10
                textSize: 24
                checked: animations_enabled.find((el) => (el == modelData) || el[modelData]) !== undefined
                backgroundColor: "gray_700_checked_pressed"
                onClicked: {
                    if (checked) {
                        config.ledstrip.animations = animations_enabled.filter((el) => !((el == modelData) || el[modelData]));
                        console.log(config.ledstrip.animations);
                    } else {
                        /* split first then second half, then insert in the middle at the right spot... */
                        var new_anims = [];
                        var me = animations_available.indexOf(modelData);
                        for (var i = 0; i < animations_enabled.length; i++) {
                            var animName = animations_enabled[i];
                            if (typeof animName != 'string') {
                                animName = Object.keys(animName)[0];
                            }
                            if (animations_available.indexOf(animName) < me) {
                                new_anims.push(animations_enabled[i]);
                            }
                        }
                        new_anims.push(modelData);
                        for (var i = 0; i < animations_enabled.length; i++) {
                            var animName = animations_enabled[i];
                            if (typeof animName != 'string') {
                                animName = Object.keys(animName)[0];
                            }
                            if (animations_available.indexOf(animName) > me) {
                                new_anims.push(animations_enabled[i]);
                            }
                        }
                        config.ledstrip.animations = new_anims;
                        console.log(config.ledstrip.animations);
                    }
                    config = config;
                    changes_pending = true;
                }
            }
            
            ScrollBar.horizontal: ScrollBar {
                policy: ScrollBar.AlwaysOn
            }
            
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AlwaysOff
            }
        }
    }
}
