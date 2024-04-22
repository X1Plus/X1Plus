import QtQuick 2.12

QtObject {
    property var handler: null
    function dbusMethodCall(method, param) {
        return handler(method, param);
    }
}

