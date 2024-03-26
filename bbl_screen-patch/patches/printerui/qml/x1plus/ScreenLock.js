.pragma library
.import DdsListener 1.0 as JSDdsListener
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;

var _DdsListener = JSDdsListener.DdsListener;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

var _screenPath;
var _lockText = 'lockscreen.txt';
var _lockImage = 'lockscreen.png';
var _brightness = 100;

var LOCK_TYPE = {
    SCREENSAVER: 0,
    SWIPE_UNLOCK: 1,
    PASSCODE_UNLOCK: 2,
};

var [screenLocked, screenLockedChanged, _setScreenLocked] = Binding.makeBinding(false);
var [passCode, passCodeChanged, _setPassCode] = Binding.makeBinding("");
var [lockType, lockTypeChanged, _setLockType] = Binding.makeBinding(LOCK_TYPE.SCREENSAVER);
var [lockText, lockTextChanged, _setLockText] = Binding.makeBinding("");
var isLock = function() { return passCode() !== "" && lockType() == LOCK_TYPE.PASSCODE_UNLOCK; };
var shouldSwipe = function() { return lockType() == LOCK_TYPE.SWIPE_UNLOCK ||  passCode()=="" };

function awaken() {
    _screenPath = `${X1Plus.printerConfigDir}/lockscreen`;
    _X1PlusNative.system("mkdir -p " + _X1PlusNative.getenv("EMULATION_WORKAROUNDS") + _screenPath);
    console.log(`[x1p] X1C Screen: filePath is ${_screenPath}`);
}
function checkCode(code){
    if (code == passCode() && code !== "" && code !== null){
        _setScreenLocked(false);
    } else {
        _setScreenLocked(true);
    }
}
function setText(txt){
    _setLockText(txt);
}

function toggleSleep(){
    if (!X1Plus.hasSleep()) {
        X1Plus.DeviceManager.power.switchSleep();
    } else {
        X1Plus.DeviceManager.power.externalWakeup();
        _setScreenLocked(true);
    }
}