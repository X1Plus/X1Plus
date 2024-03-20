.pragma library
.import DdsListener 1.0 as JSDdsListener
.import X1PlusNative 1.0 as JSX1PlusNative
.import "./x1plus/DDS.js" as X1PlusDDS
.import "./x1plus/Stats.js" as X1PlusStats
.import "./x1plus/MeshCalcs.js" as X1PlusMeshCalcs
.import "./x1plus/Binding.js" as X1PlusBinding
.import "./x1plus/GpioActions.js" as X1PlusGpioKeys
.import "./x1plus/GcodeGenerator.js" as X1PlusGcodeGenerator
.import "./x1plus/BedMeshCalibration.js" as X1PlusBedMeshCalibration
.import "./x1plus/ShaperCalibration.js" as X1PlusShaperCalibration

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

Stats.X1Plus = X1Plus;
DDS.X1Plus = X1Plus;
BedMeshCalibration.X1Plus = X1Plus;
ShaperCalibration.X1Plus = X1Plus;

var _DdsListener = JSDdsListener.DdsListener;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;
var DeviceManager = null;
var PrintManager = null;
var PrintTask = null;

var emulating = _X1PlusNative.getenv("EMULATION_WORKAROUNDS");
X1Plus.emulating = emulating;

var isIdle = null;
var hasSleep = null;
var aboutToSleep = null;



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

function sendGcode(gcode_line){
	var payload = {
		command: "gcode_line",
		param: gcode_line,
		sequence_id: "420"
	};
	DDS.publish("device/request/print", payload);
	console.log("[x1p] Gcode published:", JSON.stringify(payload));
}
X1Plus.sendGcode = sendGcode;

function GcodeMacros(macro, ...arr){
	switch (macro) { 
        case GcodeGenerator.MACROS.VIBRATION_COMP: 
            return GcodeGenerator.macros_vibrationCompensation(...arr);
        case GcodeGenerator.MACROS.BED_LEVEL:
            return GcodeGenerator.macros_ABL();
        case GcodeGenerator.MACROS.NOZZLE_CAM_PREVIEW:
            return GcodeGenerator.macros_nozzlecam();
        case GcodeGenerator.MACROS.TRAMMING:
            return GcodeGenerator.macros_tramming(...arr);
        default:
            throw new Error("Invalid macro type");
    }
}
X1Plus.GcodeMacros = GcodeMacros;

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

/* Some things can only happen after we have a DeviceManager and
 * PrintManager passed down, and the real QML environment is truly alive. 
 * These things happen from 'awaken'.
 */


function awaken(_DeviceManager, _PrintManager, _PrintTask) {
	console.log("X1Plus.js awakening");
	X1Plus.DeviceManager = _DeviceManager;
	X1Plus.PrintManager = _PrintManager;
	X1Plus.PrintTask = _PrintTask;
	BedMeshCalibration.awaken();
	ShaperCalibration.awaken();
	GpioKeys.awaken();
	// X1Plus.isIdle = _PrintManager.currentTask.stage < _PrintTask.WORKING;
	X1Plus.hasSleep = _DeviceManager.power.hasSleep;
	X1Plus.aboutToSleep= _DeviceManager.power.aboutToSleep; 
}
