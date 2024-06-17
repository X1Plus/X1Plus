.pragma library
.import "Binding.js" as Binding

/* QML interface for x1plusd OTA engine
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

var X1Plus = null;

var [status, onStatus, _setStatus] = Binding.makeBinding({});

var _CheckNow = null;
var _Download = null;
var _Update = null;

function checkNow() {
    _CheckNow({});
}

function download(base_firmware = false) {
    _Download({'base_firmware': base_firmware});
}

function update() {
    return _Update({});
}

function awaken() {
    const curStatus = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/ota", "x1plus.ota", "GetStatus")({});
    _setStatus(curStatus);

    X1Plus.DBus.onSignal("x1plus.ota", "StatusChanged", (arg) => {
        _setStatus(arg);
    });
    
    _CheckNow = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/ota", "x1plus.ota", "CheckNow");
    _Download = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/ota", "x1plus.ota", "Download");
    _Update   = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/ota", "x1plus.ota", "Update"  );
}
