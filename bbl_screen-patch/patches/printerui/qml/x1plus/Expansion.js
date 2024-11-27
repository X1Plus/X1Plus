.pragma library
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

// This probably will never change, but for consistency with other things,
// it is a binding.
var [status, _onStatus, _setStatus] = Binding.makeBinding(null);
var [database, _onDatabase, _setDatabase] = Binding.makeBinding({});

function productName() {
	return "X1Plus Expander"; // XXX: look this up in the database
}

function moduleTypeInPort(port) {
	var portStat = status();
	if (!portStat)
		return null;
	portStat = portStat && portStat['ports'] && portStat['ports'][port];
	if (!portStat)
		return null;
	// strip any digits from the revision, since the letter determines software compatibility
	return `${portStat.model}-${portStat.revision}`.replace(/[0-9]*$/, '');
}

function moduleConfiguredForPort(port) {
	var portSet = X1Plus.Settings.get(`expansion.{port}`);
	if (!portSet)
		return null;
	if (portSet && portSet['meta'] && portSet['meta']['module_configured'])
		return portSet['meta']['module_configured'];
	return "";
}

function awaken() {
	var curStatus = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/expansion", "x1plus.expansion", "GetHardware")({});
	if (X1Plus.emulating && !curStatus) {
		curStatus = {"expansion_revision": "X1P-002-B01", "expansion_serial": "X1P-002-B01-1013", "ports": {"port_a": {"model": "X1P-005", "revision": "B01", "serial": "00000001"}, "port_b": null}};
	}
	_setStatus(curStatus);
	
	_setDatabase(X1Plus.loadJson("/opt/x1plus/share/expansion/expansion.json") || {"expansions": {}, "modules": {}});
}
