.pragma library

/* This is a truly frumious hack to programmatically create bindings to
 * export from JavaScript into QML.
 */

var _componentFactory = Qt.createComponent("Bindable.qml");
var _refBindableRoot = _componentFactory.createObject(); // Otherwise, it will get GCed, and so will any of its timers attached.

/* Usage:
 *   from JavaScript: var [aBinding, onABinding, _setBinding] = Binding.makeBinding(0);
 *   later: _setBinding(aBinding() + 1);
 *   from QML: property var something = X1Plus.aBinding();
 *
 * Note that you always need the function call!  But it will still result in
 * a binding, since calling the function results in a property read from the
 * QtObject.
 */
function makeBinding(initval) {
    let obj = _componentFactory.createObject();
    obj.bound = initval;
    return [function() { return obj.bound; }, obj.boundChanged, function (v) { obj.bound = v; } ];
}

/* It appears that you cannot exfiltrate a signal, though.  Doing so results in:
 *   qrc:/printerui/qml/Screen.qml:92: Error: Function.prototype.connect: this object is not a signal
 */

// These timers permanently leak.  Be careful with them.
function makeTimer() {
    return Qt.createQmlObject("import QtQuick 2.0; Timer {}", _refBindableRoot);
}

/* Example:

let t = X1Plus.Binding.makeTimer();
t.interval = 1000;
t.repeat = true;
t.triggered.connect(() => console.log("timer trig"));
t.start();

*/
