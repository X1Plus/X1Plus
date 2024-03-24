.pragma library
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

var _fPath;
var _fName = "buttons.json";

//This needs to be removed
const ACTION_TOGGLE_SCREENSAVER = "ACTION_TOGGLE_SCREENSAVER";
const ACTION_REBOOT = "ACTION_REBOOT";
const ACTION_PAUSE_PRINT = "ACTION_PAUSE";
const ACTION_ABORT_PRINT = "ACTION_ABORT";
const ACTION_SCREENLOCK = "ACTION_SCREENLOCK";
const ACTION_RUN_MACRO = "ACTION_MACRO";

var buttonActions = [
    { name: "Reboot", val: ACTION_REBOOT },
    { name: "Screenlock", val: ACTION_SCREENLOCK },
    { name: "Pause print", val: ACTION_PAUSE_PRINT},
    { name: "Abort print", val: ACTION_ABORT_PRINT },
    { name: "Sleep/wake", val:ACTION_TOGGLE_SCREENSAVER},
    { name: "Run macro", val: ACTION_RUN_MACRO}
]

var buttonConfigs = {
    "cfw_power": {
        "shortPress": { action: ACTION_TOGGLE_SCREENSAVER, parameters: {}, default: ACTION_TOGGLE_SCREENSAVER }, 
        "longPress": { action: ACTION_REBOOT, parameters: {}, default: ACTION_REBOOT }, 
    },
    "cfw_estop": {
        "shortPress": { action: ACTION_PAUSE_PRINT, parameters: {}, default: ACTION_PAUSE_PRINT },
        "longPress": { action: ACTION_ABORT_PRINT, parameters: {}, default: ACTION_ABORT_PRINT }, 
    }
};
var gpio = ({});
var [gpioBinding, gpioChanged, _setGpio] = Binding.makeBinding(gpio);


function awaken(){
    //We should move this mkdir out of here eventually
    _fPath = `/mnt/sdcard/x1plus/printers/${X1Plus.DeviceManager.build.seriaNO}`;
    _X1PlusNative.system("mkdir -p " + _X1PlusNative.getenv("EMULATION_WORKAROUNDS") + _fPath);
    _loadSettings(false);
}

//this is a mess, can clean this up a lot more later.. 4 pretty identical getter functions! 

/**
 * Gets the action value (e.g., ACTION_REBOOT) for a specified button and press type.
 * @param {string} buttonName - The name of the button (e.g., "cfw_power").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @return {string} The action value associated with the button and press type.
 */
function getActionValue(buttonName, pressType) {
    if (buttonConfigs[buttonName] && buttonConfigs[buttonName][pressType]) {
        return buttonConfigs[buttonName][pressType].action;
    } else {
        console.log(`No action found for ${buttonName} ${pressType}.`);
        return null;
    }
}

/**
 * Retrieves the default action for a specified button and press type
 * @param {string} buttonName - The name of the button ("cfw_power" or "cfw_estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @return {string} - The default setting for the specified button event
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
 * Retrieves the default action for a specified button and press type
 * @param {string} btn - The name of the button ("cfw_power" or "cfw_estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @return {int} - The default index for the specified button event
 */
function getDefaultIndex(btn, pressType) {
    var defaultAction = buttonConfigs[btn] ? buttonConfigs[btn][pressType] ? buttonConfigs[btn][pressType].action : null : null;
    
    if (defaultAction !== null) {
        for (var i = 0; i < buttonActions.length; i++) {
            if (buttonActions[i].val === defaultAction) {
                return i;
            }
        }
    }

    return 0;
}


/*Creates a deep copy of the default settings object */
function resetToDefaultActions() {
    var defaultsApplied = JSON.parse(JSON.stringify(buttonConfigs)); 
    _setGpio(defaultsApplied); 
    X1Plus.atomicSaveJson(`/${_fPath}/${_fName}`, defaultsApplied);
    console.log("[x1p] gpio button settings restored to defaults.");
}

/**
 * Updates the action and parameters for a given button's press type.
 * @param {string} buttonName - The name of the button ("cfw_power" or "cfw_estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @param {string} actionStr - The value of the action to set.
 * @param {Object} _parameters - Parameters for the action.
 */
function updateButtonAction(buttonName, pressType, actionStr, _parameters = {}) {
    var _gpio = gpioBinding();
    if (!_gpio[buttonName] || !_gpio[buttonName][pressType]) {
        console.log(`[x1p] Invalid or missing configuration for button: ${buttonName}, pressType: ${pressType}`);
        return; 
    }
    _gpio[buttonName][pressType].action = actionStr; 
    _gpio[buttonName][pressType].parameters = _parameters;
    _gpio[buttonName][pressType].default = getDefault(buttonName, pressType);
   
    _setGpio(_gpio);
    X1Plus.atomicSaveJson(`/${_fPath}/${_fName}`, _gpio);
    return
}

/**
 * Retrieves the action text for a given button type and press type.
 * @param {string} buttonName - The name of the button ("cfw_power" or "cfw_estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @return {string} - The action text.
 */
function getActionText(buttonName, pressType) {
    var _gpio = gpioBinding();
    if (_gpio[buttonName] && _gpio[buttonName][pressType]) {
        let actionStr = _gpio[buttonName][pressType].action;
        if (actionStr) {
            console.log(`Action text for ${buttonName} ${pressType}: ${actionStr}`);
            return actionStr;
        } else {
            console.log(`[x1p] Action not found for ${buttonName}, pressType: ${pressType}.`);
        }
    }
    return "";
}

function _loadSettings(noload) {
    if (noload) return;
    let loadedSettings = X1Plus.loadJson(`/${_fPath}/${_fName}`);
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
 * @param {Object} datum
 */
function _setAction(datum) {
    var btn = '';
    var param = '';
    var _gpio = gpioBinding();
    var action_code;
    if (datum['gpio_event']) {
        btn = datum["button"] || '';
        param = datum["param"] || '';
    }
    
    if (_gpio[btn] && _gpio[btn][param]) {
        action_code = _gpio[btn][param].action;
        parameters = _gpio[btn][param].parameters;
        defaults = _gpio[btn][param].default;
    } else {
        console.log(`[x1p] gpiokeys - invalid action ${datum}`);
    }
    console.log("[x1p] gpio button", action_code,datum); 
    switch (action_code) {
        case ACTION_REBOOT:
            console.log("[x1p] Gpiokeys - Reboot");
            X1Plus.system(`reboot`);
            break;
        case ACTION_SCREENLOCK:
            X1Plus.DeviceManager.power.switchSleep();
            //need to double check this activates screenlock. might be good to check the value of power.hasSleep 
            break;
        case ACTION_PAUSE_PRINT:
            if (!X1Plus.isIdle()) { X1Plus.PrintManager.currentTask.pause() };
            console.log("[x1p] Gpiokeys - Pause print");
            break;
        case ACTION_ABORT_PRINT:
            if (!X1Plus.isIdle()) { X1Plus.PrintManager.currentTask.abort() };
            console.log("[x1p] Gpiokeys - Abort print");
            break;
        case ACTION_TOGGLE_SCREENSAVER:
            if (!X1Plus.hasSleep()) {
                X1Plus.DeviceManager.power.switchSleep();
            } else {
                X1Plus.DeviceManager.power.externalWakeup();
            }
            console.log("[x1p] Gpiokeys - toggle LCD");
            break;
        case 5: 
            console.log("[x1p] Macro executed from /opt/gpiokeys.py"); 
            // I was going to run python with a good old X1PlusNative.system() here
            break;
        default:
            console.log("[x1p] Error in parsing gpiokeys dds message");
    }
}