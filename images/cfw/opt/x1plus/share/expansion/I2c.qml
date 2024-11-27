import QtQuick 2.0
import QtQuick.Layouts 1.12
import UIBase 1.0
import Printer 1.0
import "qrc:/uibase/qml/widgets"

Text {
    font: Fonts.body_26
    color: Colors.gray_200
    wrapMode: Text.Wrap
    text: `I²C configuration is currently only available via command line.  Enabled devices: ${JSON.stringify(config.i2c)}`
}
