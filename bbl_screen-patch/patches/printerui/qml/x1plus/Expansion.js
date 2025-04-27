.pragma library
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

/* QML interface to understand the x1plusd's view of installed Expansion
 * modules
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
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

// This probably will never change, but for consistency with other things,
// it is a binding.
var [hardware, _onHardware, _setHardware] = Binding.makeBinding(null);
var [database, _onDatabase, _setDatabase] = Binding.makeBinding({});


function status() {
	// status is hardware, augmented with configuration for each port
	var rv = JSON.parse(JSON.stringify(hardware())); /* ugh.  it is OK for this to be slow, since it's in a binding usually */
	if (!rv) {
		return null;
	}
	
	rv.expansion_major = rv.expansion_revision.replace(/[0-9]*$/, '');
	
	for (var port in rv.ports) {
		// ports in the DBus response is just EEPROM content.  but
		// for users of Expansion internally, we augment this with
		// some other useful status information.
		
		if (rv.ports[port] === null) {
			// this is the DBus way of saying "no EEPROM", but
			// we might have something useful to report
			rv.ports[port] = {};
		}
		
		if (rv.ports[port].model) {
			// strip any digits from the revision, since the letter determines software compatibility
			rv.ports[port].module_detected = `${rv.ports[port].model}-${rv.ports[port].revision}`.replace(/[0-9]*$/, '');
		}
		
		rv.ports[port].config = X1Plus.Settings.get(`expansion.${port}`, {});
		rv.ports[port].module_configured = rv.ports[port].config && rv.ports[port].config.meta && rv.ports[port].config.meta.module_config;
	}
	return rv;
}

function productName() {
	var revision_maj = status().expansion_major;
	if (!database().expansions[revision_maj])
		return "Unknown expansion";
	return database().expansions[revision_maj].name;
}

function awaken() {
	var curHardware = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/expansion", "x1plus.expansion", "GetHardware")({});
	if (X1Plus.emulating && !curHardware && !_X1PlusNative.getenv("FAKE_NO_EXPANDER")) {
		curHardware = {
			"expansion_revision": _X1PlusNative.getenv("EXPANDER_REVISION") || "X1P-002-C02",
			"expansion_serial": "X1P-002-C02-1013",
			"ports": {
				"port_a": null,
				"port_b": { "model": "X1P-005", "revision": "B01", "serial": "00000001" },
				"port_c": { "model": "X1P-006", "revision": "B02", "serial": "00000001", "is_authentic": true },
				"port_d": null
			}
		};
	}
	_setHardware(curHardware);
	
	_setDatabase(X1Plus.loadJson("/opt/x1plus/share/expansion/expansion.json") || {"expansions": {}, "modules": {}});
}
