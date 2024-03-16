import QtQuick 2.0
import UIBase 1.0
import Printer 1.0

QtObject {

    //property var print: PrintManager
    property var task: PrintManager.currentTask
    property var heaters: PrintManager.heaters
    property var feeder: PrintManager.feeder

    property string input: "<stub>"
    property string value: "<stub>"

    property var object

    onInputChanged: {
        var lastObject = object;
        if (input.indexOf("${") >= 0) {
            var script = UIBase.fileContent("qrc:/printerui/qml/DynamicString.qml");
            // "xxx${a+b}yyy" -> "xxx"+(a+b)+"yyy"
            script = script.replace("<" + "stub>",
                                    input.replace(/\$\{([\w()\.\+\-\*\ \/\&\|]+)\}/g, "\"+($1)+\""))
            object = Qt.createQmlObject(script, this, "DynamicString.qml");
            value = Qt.binding(function() { return object.value })
        } else {
            value = input
            object = null
        }
        if (lastObject)
            lastObject.destroy()
    }

    property var inputs
    property var values: ["<stubs>"]

    property var objects

    onInputsChanged: {
        var lastObjects = objects;
        if (inputs.findIndex(function(e) { return e.indexOf("${") >= 0 }) >= 0) {
            var script = UIBase.fileContent("qrc:/printerui/qml/DynamicString.qml");
            script = script.replace("<" + "stubs>", inputs.map(function(i) {
                return i.replace(/\$\{([\w()\.]+)\}/g, "\"+($1)+\"")
            }).join("\",\""))
            objects = Qt.createQmlObject(script, this, "DynamicString.qml");
            values = Qt.binding(function() { return objects.values })
        } else {
            values = inputs
            objects = null
        }
        if (lastObjects)
            lastObjects.destroy()
    }
}
