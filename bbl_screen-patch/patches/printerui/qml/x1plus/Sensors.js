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

var [_status, onStatus, _setStatus] = Binding.makeBinding({});

const SENSOR_TIMEOUT = 60;

function status() {
    var tab = _status();

    // Clean out old readings.
    const now = Date.now() / 1000; // of course, that's in milliseconds, and the table is in seconds...
    for (let sensor in tab) {
        if ((now - tab[sensor]['timestamp']) > SENSOR_TIMEOUT) {
            console.log(`x1plus.sensors: remove sensor ${sensor} due to timeout`);
            delete tab[sensor];
        }
    }
    return tab;
}

function awaken() {
    const curStatus = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/sensors", "x1plus.sensors", "GetSensors")({});
    _setStatus(curStatus);

    X1Plus.DBus.onSignal("x1plus.sensors", "SensorUpdate", (arg) => {
        var tab = status();
        for (let sensor in arg) {
            tab[sensor] = arg[sensor];
        }
        _setStatus(tab);
    });
}
