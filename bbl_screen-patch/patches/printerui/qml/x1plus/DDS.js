.pragma library
.import DdsListener 1.0 as JSDdsListener
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;

var _DdsListener = JSDdsListener.DdsListener;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

function publish(topic, json) {
    _DdsListener.publishJson(topic, JSON.stringify(json));
}

var _handlers = [];
function registerHandler(topic, callback) {
    _handlers.push({ topic: topic, fn: callback });
}

_DdsListener.gotDdsEvent.connect(function(topic, message) {
    var data = null;
    for (const i in _handlers) {
        const handler = _handlers[i];
        if (handler.topic == topic) {
            if (data == null) {
                data = JSON.parse(message);
            }
            handler.fn(data);
        }
    }
});


var [versions, versionsChanged, _setVersions] = Binding.makeBinding([]);

function requestVersions() {
    publish("device/request/info", {"command": "get_version", "sequence_id": "0" });
    if (X1Plus.emulating) {
        _setVersions([
            {"hw_ver":"","name":"ota","sn":"","sw_ver":"01.05.01.00"},
            {"hw_ver":"AP05","name":"rv1126","sn":"00M00A9A9999999","sw_ver":"00.00.19.15"},
            {"hw_ver":"TH09","name":"th","sn":"00301B9A9999999","sw_ver":"00.00.04.98"},
            {"hw_ver":"MC07","name":"mc","sn":"00201A9A9999999","sw_ver":"00.00.14.44/00.00.14.44"},
            {"hw_ver":"","name":"xm","sn":"","sw_ver":"00.01.02.00"},
            {"hw_ver":"AHB00","name":"ahb","sn":"00K00A999999999","sw_ver":"00.00.00.42"},
            {"hw_ver":"AMS08","name":"ams/0","sn":"00600A999999998","sw_ver":"00.00.06.15"},
            {"hw_ver":"AMS08","name":"ams/1","sn":"00600A999999999","sw_ver":"00.00.06.15"}
        ]);
    }
}

registerHandler("device/report/info", function(datum) {
    if (datum.command == "get_version") {
        _setVersions(datum.module);
    }
});


var [gcodeAction, gcodeActionChanged, _setGcodeAction] = Binding.makeBinding(-1);

registerHandler("device/report/print", function(datum) {
    if (datum.command == "push_status" && datum.print_gcode_action) {
        if (gcodeAction() != datum.print_gcode_action) {
            _setGcodeAction(datum.print_gcode_action);
        }
    }
});
