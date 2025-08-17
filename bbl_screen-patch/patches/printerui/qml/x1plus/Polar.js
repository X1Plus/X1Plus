.pragma library
.import "Binding.js" as Binding

/* QML interface for x1plusd sensors
 *
 * Copyright (c) 2025 Joshua Wise, and the X1Plus authors.
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

var _Login = null;
var _Logout = null;

function login(username, pin) {
    return _Login({'username': username, 'pin': pin});
}

function logout() {
    _Logout({});
}

function awaken() {
    // it would be good to have a better timeout on this so that screen
    // doesn't hang on boot for ~10sec if the Polar module is disabled, but
    // oh well
    const curStatus = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/polar", "x1plus.polar", "GetStatus")({});
    _setStatus(curStatus);

    X1Plus.DBus.onSignal("x1plus.polar", "StatusChanged", (arg) => {
        _setStatus(arg);
    });

    _Login  = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/polar", "x1plus.polar", "Login" );
    _Logout = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/polar", "x1plus.polar", "Logout");
}
