.pragma library

/* Core logic to mirror x1plusd settings to QML bindings
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

var _PutSettings = null;
var _settings = {};
var _settingsBindings = {};

function _settingChanged(k, v) {
    _settings[k] = v;
    if (_settingsBindings[k]) {
        _settingsBindings[k][2 /* set */](v);
    }
}

function get(k, def) {
    if (!_settingsBindings[k]) {
        _settingsBindings[k] = X1Plus.Binding.makeBinding(_settings[k]);
    }
    var v = _settingsBindings[k][0 /* get */](); /* trigger the binding */
    if (v === undefined || v === null) {
        return def;
    } else {
        return v;
    }
}

function put(k, v) {
    _settingChanged(k, v);
    _PutSettings({ [k]: v });
}

function _migrate(k, newk) {
    var v = X1Plus.DeviceManager.getSetting(k, null);
    if (v !== null) {
        console.log(`X1Plus.Settings: migrating key ${k} -> ${newk}`);
        put(newk, v);
        X1Plus.DeviceManager.putSetting(k, null);
    }
}

function awaken() {
    X1Plus.DBus.onSignal("x1plus.settings", "SettingsChanged", (arg) => {
        for (const k in arg) {
            console.log(`x1plus.settings.SettingsChanged(${k})`);
            _settingChanged(k, arg[k]);
        }
    });
    _settings = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/settings", "x1plus.settings", "GetSettings")() || {};
    _PutSettings = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/settings", "x1plus.settings", "PutSettings");
    
    for (const k in _settings) {
        // did someone beat us to it??
        if (_settingsBindings[k]) {
            _settingsBindings[k][2 /* set */](_settings[k]);
        }
    }

    _migrate("cfw_passcode", "lockscreen.passcode");
    _migrate("cfw_locktype", "lockscreen.mode");
    _migrate("cfw_lockscreen_image", "lockscreen.image");
    _migrate("cfw_home_image", "homescreen.image");
    _migrate("cfw_print_image", "homescreen.image.printing");
    _migrate("cfw_rootpw", "ssh.root_password");
    _migrate("cfw_sshd", "ssh.enabled");
}
