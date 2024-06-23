.pragma library
.import DdsListener 1.0 as JSDdsListener
.import X1PlusNative 1.0 as JSX1PlusNative
.import "./x1plus/DDS.js" as X1PlusDDS
.import "./x1plus/Stats.js" as X1PlusStats
.import "./x1plus/MeshCalcs.js" as X1PlusMeshCalcs
.import "./x1plus/Binding.js" as X1PlusBinding
.import "./x1plus/GpioKeys.js" as X1PlusGpioKeys
.import "./x1plus/GcodeGenerator.js" as X1PlusGcodeGenerator
.import "./x1plus/BedMeshCalibration.js" as X1PlusBedMeshCalibration
.import "./x1plus/ShaperCalibration.js" as X1PlusShaperCalibration
.import "./x1plus/DBus.js" as X1PlusDBus
.import "./x1plus/Settings.js" as X1PlusSettings
.import "./x1plus/TempGraph.js" as X1PlusTempGraph
.import "./x1plus/OTA.js" as X1PlusOTA
.import "./x1plus/Network.js" as X1PlusNetwork

/* Back-end model logic for X1Plus's UI
 *
 * Copyright (c) 2023 - 2024 Joshua Wise, and the X1Plus authors.
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

console.log("X1Plus.js starting up");

var X1Plus = X1Plus || {};
/* Reexport all our imports.  If you name them Stats and then attempt to
 * shadow them with a var, you will lose in bizarre ways.  */
X1Plus.Stats = X1PlusStats;
var Stats = X1PlusStats;
X1Plus.Binding = X1PlusBinding;
var Binding = X1PlusBinding;
X1Plus.MeshCalcs = X1PlusMeshCalcs;
var MeshCalcs = X1PlusMeshCalcs;
X1Plus.DDS = X1PlusDDS;
var DDS = X1PlusDDS;
X1Plus.GcodeGenerator = X1PlusGcodeGenerator;
var GcodeGenerator = X1PlusGcodeGenerator;
X1Plus.BedMeshCalibration = X1PlusBedMeshCalibration;
var BedMeshCalibration = X1PlusBedMeshCalibration;
X1Plus.ShaperCalibration = X1PlusShaperCalibration;
var ShaperCalibration = X1PlusShaperCalibration;
X1Plus.GpioKeys = X1PlusGpioKeys;
var GpioKeys  = X1PlusGpioKeys;
X1Plus.DBus = X1PlusDBus;
var DBus = X1PlusDBus;
X1Plus.Settings = X1PlusSettings;
var Settings = X1PlusSettings;
X1Plus.TempGraph = X1PlusTempGraph;
var TempGraph = X1PlusTempGraph;
X1Plus.OTA = X1PlusOTA;
var OTA = X1PlusOTA;
X1Plus.Network = X1PlusNetwork;
var Network = X1PlusNetwork;

Stats.X1Plus = X1Plus;
DDS.X1Plus = X1Plus;
BedMeshCalibration.X1Plus = X1Plus;
ShaperCalibration.X1Plus = X1Plus;
GpioKeys.X1Plus = X1Plus;
DBus.X1Plus = X1Plus;
Settings.X1Plus = X1Plus;
TempGraph.X1Plus = X1Plus;
OTA.X1Plus = X1Plus;
Network.X1Plus = X1Plus;

var _DdsListener = JSDdsListener.DdsListener;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;
var DeviceManager = null;
var PrintManager = null;
var NetworkManager = null;
var PrintTask = null;
var NetworkEnum = null;
var printerConfigDir = null;

var emulating = _X1PlusNative.getenv("EMULATION_WORKAROUNDS");
X1Plus.emulating = emulating;


function isIdle() {
	return PrintManager.currentTask.stage < PrintTask.WORKING;
}
X1Plus.isIdle = isIdle;

function hasSleep() {
	return DeviceManager.power.hasSleep;
}
X1Plus.hasSleep = hasSleep;

function loadJson(path) {
	let xhr = new XMLHttpRequest();
	xhr.open("GET", "file:///" + emulating + path, /* async = */ false);
	xhr.responseType = "json";
	xhr.send();
	if (xhr.status != 200)
		return null;
	return xhr.response;
}
X1Plus.loadJson = loadJson;

function saveJson(path, json) {
	_X1PlusNative.saveFile(emulating + path, JSON.stringify(json));
}
X1Plus.saveJson = saveJson;

function atomicSaveJson(path, json) {
	_X1PlusNative.atomicSaveFile(emulating + path, JSON.stringify(json));
}
X1Plus.atomicSaveJson = atomicSaveJson;

function sendGcode(gcode_line,seq_id = 0){
	
	var payload = {
		command: "gcode_line",
		param: gcode_line,
		sequence_id: seq_id
	};
	DDS.publish("device/request/print", payload);
	console.log("[x1p] Gcode published:", JSON.stringify(payload));
}
X1Plus.sendGcode = sendGcode;

function formatTime(time) {
	return new Date(time * 1000).toLocaleString('en-US', {
        	year: 'numeric', 
        	month: 'short', 
        	day: 'numeric',
        	hour: '2-digit',
        	minute: '2-digit', 
        	hour12: false
	});
}
X1Plus.formatTime = formatTime;

function fileExists(fPath) {
    return _X1PlusNative.popen(`test -f ${fPath} && echo 1 || echo 0`) == "1";
}
X1Plus.fileExists = fileExists;

/* Some things can only happen after we have a DeviceManager and
 * PrintManager passed down, and the real QML environment is truly alive. 
 * Submodules also don't get access to the global X1Plus object until after
 * they are loaded, and they might need to do work touching other modules. 
 * These things happen from 'awaken'.
 */
function awaken(_DeviceManager, _PrintManager, _NetworkManager, _PrintTask, _Network) {
	console.log("X1Plus.js awakening");
	X1Plus.DeviceManager = DeviceManager = _DeviceManager;
	X1Plus.PrintManager = PrintManager = _PrintManager;
	X1Plus.NetworkManager = NetworkManager = _NetworkManager;
	X1Plus.PrintTask = PrintTask = _PrintTask;
	X1Plus.NetworkEnum = NetworkEnum = _Network;
	X1Plus.printerConfigDir = printerConfigDir = `/mnt/sdcard/x1plus/printers/${X1Plus.DeviceManager.build.seriaNO}`;
	_X1PlusNative.system("mkdir -p " + _X1PlusNative.getenv("EMULATION_WORKAROUNDS") + printerConfigDir);
	Settings.awaken();
	OTA.awaken();
	BedMeshCalibration.awaken();
	ShaperCalibration.awaken();
	GpioKeys.awaken();
	TempGraph.awaken();
	Network.awaken();
	console.log("X1Plus.js is awake");
}

X1Plus.DBus.registerMethod("ping", (param) => {
	param["pong"] = "from QML";
	return param;
});
X1Plus.DBus.onSignal("x1plus.screen", "log", (param) => console.log(param.text));
X1Plus.DBus.registerMethod("TryRpc", (param) => {
	console.log("trying an RPC to x1plus hello daemon");
	var f = X1Plus.DBus.proxyFunction("x1plus.hello", "/x1plus/hello", "x1plus.hello", "PingPong");
	param["resp"] = f("hello");
	return param;
});
