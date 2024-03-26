.pragma library
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

const CONFIG_FILE = "buttons.json";
// var lastEventTime = 0;  //delete if debouncing not needed
// const DEBOUNCE_INTERVAL = 500;  
const ACTION_TOGGLE_SCREENSAVER = "ACTION_TOGGLE_SCREENSAVER";
const ACTION_REBOOT = "ACTION_REBOOT";
const ACTION_PAUSE_PRINT = "ACTION_PAUSE";
const ACTION_ABORT_PRINT = "ACTION_ABORT";
const ACTION_SCREENLOCK = "ACTION_SCREENLOCK";
const ACTION_RUN_MACRO = "ACTION_MACRO";

const DEFAULTS = {
    "power": { "shortPress": { action: ACTION_TOGGLE_SCREENSAVER }, "longPress": { action: ACTION_REBOOT } },
    "estop": { "shortPress": { action: ACTION_PAUSE_PRINT }, "longPress": { action: ACTION_ABORT_PRINT } }
};

const BUTTON_ACTIONS = [
    { name: QT_TR_NOOP("Sleep/wake"), val: ACTION_TOGGLE_SCREENSAVER },
    { name: QT_TR_NOOP("Reboot"), val: ACTION_REBOOT },
    { name: QT_TR_NOOP("Lock screen"), val: ACTION_SCREENLOCK },
    { name: QT_TR_NOOP("Pause print"), val: ACTION_PAUSE_PRINT},
    { name: QT_TR_NOOP("Abort print"), val: ACTION_ABORT_PRINT },
    /* { name: QT_TR_NOOP("Run macro"), val: ACTION_RUN_MACRO }, */
];

const BUTTON_MAPPING_OLD = {
    "0": ACTION_REBOOT,
    /* "1": SET_TEMP no longer exists */
    "2": ACTION_PAUSE_PRINT,
    "3": ACTION_ABORT_PRINT,
    "4": ACTION_TOGGLE_SCREENSAVER,
    /* "5": nozzle cam no longer exists */
    /* "6": run macro no longer exists */
};

var [keyBindings, keyBindingsChanged, _setKeyBindings] = Binding.makeBinding({});

/**
 * Looks up the current binding for a specific action, or returns a default if none exists.
 * @param {string} buttonName - The name of the button (e.g., "power").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @return {string} The action value associated with the button and press type.
 */
function getBinding(buttonName, pressType) {
    var _gpio = keyBindings();
    return (_gpio[buttonName] && _gpio[buttonName][pressType]) || (DEFAULTS[buttonName] && DEFAULTS[buttonName][pressType]);
}


/*Creates a deep copy of the default settings object */
function resetToDefaultActions() {
    _setKeyBindings(JSON.parse(JSON.stringify(DEFAULTS)));
    _saveSettings();
    console.log("[x1p] gpio button settings restored to defaults.");
}

/**
 * Updates the action and parameters for a given button's press type.
 * @param {string} buttonName - The name of the button ("power" or "estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 * @param {string} actionStr - The value of the action to set.
 * @param {Object} _parameters - Parameters for the action.
 */
function setBinding(buttonName, pressType, actionStr, _parameters = {}) {
    /* Do a read-modify-write to avoid blowing away user changes to the JSON file. */
    _loadSettings();

    var _gpio = keyBindings();
    if (!_gpio[buttonName] || !_gpio[buttonName][pressType]) {
        console.log(`[x1p] Invalid or missing configuration for button: ${buttonName}, pressType: ${pressType}`);
        return; 
    }
    _gpio[buttonName][pressType].action = actionStr; 
    _gpio[buttonName][pressType].parameters = _parameters;
    _setKeyBindings(keyBindings());

    _saveSettings();
}

function _mapOldSetting(old, newbtn, newpress) {
    var oldSetting = X1Plus.DeviceManager.getSetting(old);
    if (oldSetting !== null && oldSetting !== undefined && BUTTON_MAPPING_OLD[oldSetting]) {
        setBinding(newbtn, newpress, BUTTON_MAPPING_OLD[oldSetting]);
        X1Plus.DeviceManager.putSetting(old, undefined);
    }
}

function _loadSettings() {
    let loadedSettings = X1Plus.loadJson(`${X1Plus.printerConfigDir}/${CONFIG_FILE}`);
    if (loadedSettings && Object.keys(loadedSettings).length > 0) {
        console.log("[x1p] Loaded key bindings:", JSON.stringify(loadedSettings));
        _setKeyBindings(loadedSettings);
    } else {
        console.log("[x1p] no settings file found. loading default actions.");
        resetToDefaultActions();
        _mapOldSetting("cfw_power_short", "power", "shortPress");
        _mapOldSetting("cfw_power_long",  "power", "longPress");
        _mapOldSetting("cfw_estop_short", "estop", "shortPress");
        _mapOldSetting("cfw_estop_long",  "estop", "longPress");
    }
}

function _saveSettings() {
    X1Plus.atomicSaveJson(`${X1Plus.printerConfigDir}/${CONFIG_FILE}`, keyBindings());
    console.log("[x1p] Saved key bindings:", JSON.stringify(keyBindings()));
}

/**
 * handle button action given dds message
 * @param {string} button - The name of the button ("power" or "estop").
 * @param {string} pressType - The type of press ("shortPress" or "longPress").
 */
function _handleButton(button, event) {
    var _gpio = keyBindings();
    var config = getBinding(button, event);
    // 
    // var currentTime = new Date().getTime();
    // if (currentTime - lastEventTime < DEBOUNCE_INTERVAL) {
    //     console.log(lastEventTime,currentTime);
    //     return;
    // }
    if (!config) {
        console.log(`[x1p] gpiokeys - invalid action ${button} / ${event}`);
        return;
    }
    console.log("[x1p] gpio button", config.action, button, event); 
    switch (config.action) {
        case ACTION_REBOOT:
            console.log("[x1p] Gpiokeys - Reboot");
            _X1PlusNative.system(`reboot`);
            break;
        case ACTION_SCREENLOCK:
            X1Plus.ScreenLock.toggleSleep();
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
            break;
        default:
            console.log("[x1p] Error parsing gpiokeys dds message");
    }

    lastEventTime = currentTime;
}

function awaken(){
    _loadSettings();
    X1Plus.DDS.registerHandler("device/x1plus", function(datum) {
        console.log("device/x1plus", datum);
            if (datum.gpio) {
                _handleButton(datum.gpio.button, datum.gpio.event);
                return;
            }
    });
}
