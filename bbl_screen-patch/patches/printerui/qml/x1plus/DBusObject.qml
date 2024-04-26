import QtQuick 2.12

QtObject {
    property var methodCallHandler: null
    property var signalHandler: null
    function dbusMethodCall(method, param) {
        return methodCallHandler(method, param);
    }
    function dbusSignal(path, name, param) {
        signalHandler(path, name, param);
    }
}

