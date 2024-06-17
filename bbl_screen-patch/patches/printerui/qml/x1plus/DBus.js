.pragma library
.import DBusListener 1.0 as JSDBusListener

/* Glue logic to connect Bambu DBus to QML
 *
 * Copyright (c) 2024 Joshua Wise, and the X1Plus authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


var _DBusListener = JSDBusListener.DBusListener;

var X1Plus = null;

var _componentFactory = Qt.createComponent("DBusObject.qml");
var _DBusObject = _componentFactory.createObject();

var _methods = {};
var _signals = {};

_DBusObject.methodCallHandler = (method, param) => {
    var fn = _methods[method];
    if (!fn) {
        console.log(`*** handleDbusMethodCall got invalid method ${method} -- this should not be!`);
        return;
    }
    return JSON.stringify(fn(JSON.parse(param)));
};
_DBusObject.signalHandler = (path, name, param) => {
    var p = `${path}.${name}`;
    param = JSON.parse(param);
    if (_signals[p]) {
        for (const fn of _signals[p]) {
            fn(param);
        } 
    }
};
_DBusListener.handler = _DBusObject; // ugh

function registerMethod(name, fn) {
    if (_methods[name]) {
        console.log(`*** X1Plus.DBus.registerMethod called twice for ${name}?`);
    } else {
        _DBusListener.registerMethod(name);
    }
    _methods[name] = fn;
}

function onSignal(path, name, fn) {
    var p = `${path}.${name}`;
    if (!_signals[p]) {
        _signals[p] = [];
        _DBusListener.registerSignal(path, name);
    }
    _signals[p].push(fn);
}

var _proxies = {};

function proxyFunction(busName, objName, interface, method) {
    if (!_proxies[busName]) {
        _proxies[busName] = {};
    }
    if (!_proxies[busName][objName]) {
        _proxies[busName][objName] = _DBusListener.createProxy(busName, objName);
    }
    return (j) => {
        if (j === undefined)
            j = null;
        var s = _proxies[busName][objName].callMethod(interface, method, JSON.stringify(j));
        try {
            return JSON.parse(s);
        } catch (e) {
            console.log(`DBus method invocation (${objName} ${interface}.${method}) failed: ${s}`);
            return null;
        }
    };
}
