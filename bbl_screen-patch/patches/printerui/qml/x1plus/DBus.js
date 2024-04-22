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

function _handleDbus(method, param) {
    var fn = _methods[method];
    if (!fn) {
        console.log(`*** handleDbus got invalid method ${method} -- this should not be!`);
        return;
    }
    return JSON.stringify(fn(JSON.parse(param)));
}
_DBusObject.handler = _handleDbus; // ugh
_DBusListener.handler = _DBusObject;

function registerMethod(name, fn) {
    if (_methods[name]) {
        console.log(`*** X1Plus.DBus.registerMethod called twice for ${name}?`);
    } else {
        _DBusListener.registerMethod(name);
    }
    _methods[name] = fn;
}
