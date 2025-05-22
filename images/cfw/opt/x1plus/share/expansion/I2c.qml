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
    Layout.fillWidth: true
    
    property var devices_available: [
        [ 0x44, { "sht41": {} } ],
        [ 0x34, { "tca8418": { "rows": 4, "cols": 4 } } ],
        [ 0x38, { "aht20": {} } ],
        [ 0x12, { "pmsa003i": {} } ],
    ]

    Text {
        Layout.fillWidth: true
        font: Fonts.body_26
        color: Colors.gray_200
        wrapMode: Text.Wrap
        text: `I²C configuration through the GUI is very limited.  For advanced configuration, use the x1plusd settings command line.  Enabled devices: ${JSON.stringify(config.i2c)}`
    }
    
    // config.i2c may have the address in a different base; find the string
    // key that matches, based on an int address
    function findAddress(address) {
        return Object.keys(config.i2c).find((key) => parseInt(key) == address) || address;
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        
        Text {
            font: Fonts.body_26
            color: Colors.gray_200
            wrapMode: Text.Wrap
            text: qsTr("<b>Enabled drivers:</b>")
        }
        
        /* This removes a lot of the flexibility of the configuration
         * system, but so be it.  If you made changes by hand, this will
         * probably blow them away.  */
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            orientation: ListView.Horizontal
            model: devices_available
            clip: true
            spacing: 12
            
            delegate: ZButton {
                property var address: modelData[0]
                property var drvconfig: modelData[1]
                property var driver: Object.keys(drvconfig)[0]
                text: Object.keys(modelData[1])[0]
                height: ListView.view.height - 10
                textSize: 24
                checked: Object.keys(config.i2c[findAddress(address)] || { '': {} })[0] == driver
                backgroundColor: "gray_700_checked_pressed"
                onClicked: {
                    if (checked) {
                        delete config.i2c[findAddress(address)];
                    } else {
                        config.i2c[`0x${address.toString(16).padStart(2, '0')}`] = drvconfig;
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
