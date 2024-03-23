.pragma library
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;


var settings_file = "/mnt/sdcard/x1plus/buttons.json"

const ACTION_TOGGLE_SCREENSAVER = "Sleep/wake";
const ACTION_REBOOT = "Reboot";
const ACTION_PAUSE_PRINT = "Pause print";
const ACTION_ABORT_PRINT = "Abort print";
const ACTION_SET_TEMP = "Set temp";
const ACTION_RUN_MACRO = "Run macro";

var buttonActions = [
    { name: "Reboot", val: 0 },
    { name: "Set temp", val: 1 },
    { name: "Pause print", val: 2 },
    { name: "Abort print", val: 3 },
    { name: "Sleep/wake", val: 4 },
    { name: "Run macro", val: 5 }
];
var buttonConfigs = {
    "cfw_power": {
        "shortPress": { action: 4, parameters: {}, default: 4 }, 
        "longPress": { action: 0, parameters: {}, default: 0 }, 
    },
    "cfw_estop": {
        "shortPress": { action: 2, parameters: {}, default: 2 },
        "longPress": { action: 3, parameters: {}, default: 3 }, 
    }
};
var gpio = ({});
var [gpioBinding, gpioChanged, _setGpio] = Binding.makeBinding(gpio);


function awaken(){
    _loadSettings(false);
}


/**
 * Retrieves the default action for a specified button and press type
 * @param {string} buttonName - The name of the button ("cfw_power" or "cfw_estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @return {int} - The default setting for the specified button event
 */
function getDefault(btn, pressType) {
    if (buttonConfigs[btn] && buttonConfigs[btn][pressType]) {
        return buttonConfigs[btn][pressType].default;
    } else {
        console.log(`Configuration for ${btn} ${pressType} not found.`);
        return "";
    }
}


/**
 * Creates a deep copy of the default settings object
 * @return {Object} - Object after defaults are applied
 */
function resetToDefaultActions() {
    var defaultsApplied = JSON.parse(JSON.stringify(buttonConfigs)); 
    _setGpio(defaultsApplied); 
    X1Plus.atomicWriteJson(settings_file, defaultsApplied);
    console.log("[x1p] gpio button settings restored to defaults.");
    return defaultsApplied; 
}

/**
 * Updates the action and parameters for a given button's press type.
 * @param {string} buttonName - The name of the button ("cfw_power" or "cfw_estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @param {number} actionVal - The value of the action to set.
 * @param {Object} _parameters - Parameters for the action.
 */
function updateButtonAction(buttonName, pressType, actionVal, _parameters = {}) {
    var _gpio = gpioBinding();
    if (!_gpio[buttonName] || !_gpio[buttonName][pressType]) {
        console.log(`[x1p] Invalid or missing configuration for button: ${buttonName}, pressType: ${pressType}`);
        return; 
    }
    let actionObject = buttonActions.find(a => a.val === actionVal);
    if (!actionObject) {
        console.log(`[x1p] Action value ${actionVal} not found in buttonActions.`);
        return;
    }
    _gpio[buttonName][pressType].action = actionVal; 
    _gpio[buttonName][pressType].parameters = _parameters;
    _gpio[buttonName][pressType].default = getDefault(buttonName,pressType);
   
    _setGpio(_gpio);
    X1Plus.atomicWriteJson(settings_file, _gpio);
}



/**
 * Retrieves the action text for a given button type and press type.
 * @param {string} buttonName - The name of the button ("cfw_power" or "cfw_estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @return {string} - The action text.
 */
function getActionText(buttonName, pressType) {
    if (!buttonName || !pressType) {
        return "";
    }
    var _gpio = gpioBinding();
    if (_gpio[buttonName] && _gpio[buttonName][pressType]) {
        let actionVal = _gpio[buttonName][pressType].action;
        let actionObject = buttonActions.find(a => a.val === actionVal);
        if (actionObject) {
            console.log(`Action text for ${buttonName} ${pressType}: ${actionObject.name}`);
            return actionObject.name;
        } else {
            console.log(`Action value ${actionVal} not found in buttonActions for ${buttonName} ${pressType}.`);
        }
    } else {
        console.log(`[x1p] Action not mapped for ${buttonName}, pressType: ${pressType}.`);
    }
    return "";
}


function _loadSettings(noload) {
    if (noload) return;
    let loadedSettings = X1Plus.loadJson(settings_file);
    if (loadedSettings && Object.keys(loadedSettings).length > 0) {
        console.log("[x1p] Loaded settings:", JSON.stringify(loadedSettings));
        _setGpio(loadedSettings);
    } else {
        console.log("[x1p] no settings file found. loading default actions.");
        resetToDefaultActions(); 
    }
}

/**
 * handle button action given dds message
 * @param {string} action_code
 * @param {string} datum
 */
function handleAction(action_code, datum) {
    console.log("[x1p] gpio button", action_code,datum); 
    switch (action_code) {
        case ACTION_REBOOT:
            console.log("[x1p] Gpiokeys - Reboot");
            X1Plus.system(`reboot`);
            break;
        case ACTION_SET_TEMP:
            var setT;
            if (!X1Plus.isIdle) { return };
            let params = datum["param"];
            if (params.nozzle) {
                setT = parseInt(params.nozzle);
                if (setT <= 300 && setT > 0) {
                    X1Plus.sendGcode(`M104 S${setT}`);
                    console.log("[x1p] Gpiokeys - Preheat nozzle to ", setT);
                }
            } else if (params.bed) {
                setT = parseInt(params.bed);
                if (setT <= 110 && setT > 0) {
                    X1Plus.sendGcode(`M140 S${setT}`);
                    console.log("[x1p] Gpiokeys - Preheat bed to ", setT);
                }
            }
            break;
        case ACTION_PAUSE_PRINT:
            if (!X1Plus.isIdle) { X1Plus.PrintManager.currentTask.pause() };
            console.log("[x1p] Gpiokeys - Pause print");
            break;
        case ACTION_ABORT_PRINT:
            if (!X1Plus.isIdle) { X1Plus.PrintManager.currentTask.abort() };
            console.log("[x1p] Gpiokeys - Abort print");
            break;
        case ACTION_TOGGLE_SCREENSAVER:
            if (!X1Plus.hasSleep) {
                X1Plus.DeviceManager.power.switchSleep();
            } else {
                X1Plus.DeviceManager.power.externalWakeup();
            }
            console.log("[x1p] Gpiokeys - toggle LCD");
            break;
        case 5:
            console.log("[x1p] Macro executed from /opt/gpiokeys.py");
            break;
        default:
            console.log("[x1p] Error in parsing gpiokeys dds message");
    }
}