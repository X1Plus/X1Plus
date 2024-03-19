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
        if (input.indexOf("${") >= 0) {
            var replinput = '"' + input.replace(/\$\{([\w()\.\+\-\*\ \/\&\|]+)\}/g, "\"+($1)+\"") + '"';
            value = Qt.binding(function() { return eval(replinput) })
        } else {
            value = input
        }
    }

    property var inputs
    property var values: ["<stubs>"]

    onInputsChanged: {
        if (inputs.findIndex(function(e) { return e.indexOf("${") >= 0 }) >= 0) {
            var replinput = inputs.map(function(i) {
                return '"' + i.replace(/\$\{([\w()\.\+\-\*\ \/\&\|]+)\}/g, "\"+($1)+\"") + '"'
            })
            values = Qt.binding(function() { return replinput.map(function(i) { return eval(i); } ); })
        } else {
            values = inputs
        }
    }
}
