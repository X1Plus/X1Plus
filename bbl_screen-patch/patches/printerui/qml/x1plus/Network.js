.pragma library
.import "Binding.js" as Binding

/* Mechanism to fake a wiredNetwork even when the bbl_screen C++ does not
 * want to give it to us
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

var [_wiredStatus, _onWiredStatus, _setWiredStatus] = Binding.makeBinding(undefined);

function wiredNetwork() {
	if (!X1Plus.NetworkManager) {
		console.log("*** Network.js: UGH we lost the race");
	}
	if (X1Plus && X1Plus.NetworkManager && X1Plus.NetworkManager.wiredNetwork !== undefined) {
		return X1Plus.NetworkManager.wiredNetwork;
	}
	return _wiredStatus();
}

function awaken() {
	X1Plus.DDS.registerHandler("device/inter/report/netservice", function(datum) {
		/* wiredStatus needs to have:
		 *   .state (Network.CONNECTED, DISABLE, DISCONNECTED)
		 *   .isOn
		 *   .powerState
		 *   .macAddr
		 *   .ipv4, .gateway, .mask, .dns, .dns2
		 *   .isManualDHCP
		 */
		if (datum.dev_list) {
			for (const n of datum.dev_list) {
				if (n.dev_name != "eth0")
					continue;
				
				let newStatus = {};
				newStatus.state =
					n.state == "DISABLE" ? X1Plus.NetworkEnum.DISABLE :
					n.state == "DISCONNECTED" ? X1Plus.NetworkEnum.DISCONNECTED :
					n.state == "CONNECTING" ? X1Plus.NetworkEnum.CONNECTING :
					n.state == "CONFIG" ? X1Plus.NetworkEnum.CONFIG :
					n.state == "CONNECTED" ? X1Plus.NetworkEnum.CONNECTED :
					n.state == "CONNECT_FAILED" ? X1Plus.NetworkEnum.CONNECT_FAILED :
					X1Plus.NetworkEnum.DISCONNECTED;
				newStatus.isOn = n.net_switch == "ON";
				newStatus.powerState = n.power_state == "enable";
				newStatus.isManualDHCP = n.manual_ip;
				newStatus.macAddr = n.mac;
				newStatus.ipv4 = n.ip;
				newStatus.gateway = n.gw;
				newStatus.mask = n.mask;
				newStatus.dns = n.dns1;
				newStatus.dns2 = n.dns2;
				newStatus.domain = n.domain;
				_setWiredStatus(newStatus);
			}
		}
	});
}
