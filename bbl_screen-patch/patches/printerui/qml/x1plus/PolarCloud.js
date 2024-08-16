.pragma library
.import "Binding.js" as Binding

/* QML interface for x1plusd polar engine
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

var _Unregister = null;
var _Register = null;
var _Update = null;



function awaken() {
    const curStatus = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/polar", "x1plus.polar", "GetStatus")({});
    _setStatus(curStatus);

    X1Plus.DBus.onSignal("x1plus.polar", "StatusChanged", (arg) => {
        _setStatus(arg);
    });
    // fns like these will also be used to get input from the screen.
    _PrintFile = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/polar", "x1plus.polar", "PrintFile");
    // _Download = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/polar", "x1plus.polar", "Download");
    // _Update   = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/polar", "x1plus.polar", "Update"  );
}


// PrintManager.currentTask.stage

// gcode_file
