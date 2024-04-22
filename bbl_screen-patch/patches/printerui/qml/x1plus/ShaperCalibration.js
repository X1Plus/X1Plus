.pragma library
.import DdsListener 1.0 as JSDdsListener
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;

var _DdsListener = JSDdsListener.DdsListener;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

var _logPath;
var _fName = 'vibration_comp.json';

var STATUS = {
    IDLE: 0,
    STARTING: 1,
    SWEEPING: 2,
    TIMED_OUT: 3,
    DONE: 4
};

var [status, statusChanged, _setStatus] = Binding.makeBinding(STATUS.IDLE);
var [shaperData, shaperDataChanged, _setShaperData] = Binding.makeBinding(null);
var [currentRangeLow, currentRangeLowChanged, _setCurrentRangeLow] = Binding.makeBinding(null);
var [currentRangeHigh, currentRangeHighChanged, _setCurrentRangeHigh] = Binding.makeBinding(null);
var [_axisAndFreq, _axisAndFreqChanged, _setAxisAndFreq] = Binding.makeBinding([null, null]); // These get updated atomically together.
var currentAxis = function() { return _axisAndFreq()[0]; }
var lastFrequency = function() { return _axisAndFreq()[1]; }
var [lastCalibrationTime, lastCalibrationTimeChanged, _setLastCalibrationTime] = Binding.makeBinding(null);
var isActive = function() { return status() == STATUS.STARTING || status() == STATUS.SWEEPING; };

function awaken() {
    _logPath = `${X1Plus.printerConfigDir}/logs`;
    _X1PlusNative.system("mkdir -p " + _X1PlusNative.getenv("EMULATION_WORKAROUNDS") + _logPath);
    console.log(`[x1p] ShaperCalibration: logPath is ${_logPath}`);
    try {
        _loadDatabase();
    } catch (e) {
        console.log("[x1p] ShaperCalibration: failed to load database; erasing");
        _loadDatabase(true);
    }
}

/*** Calibration capture ***/

const TIMEOUT_FIRST_POINT_MS = 90000;
const TIMEOUT_POINT_MS = 5000;

var _isFinishing = false;
var _finishVcParamCount = 0;

var _timeoutTimer = Binding.makeTimer();
_timeoutTimer.repeat = false;
_timeoutTimer.triggered.connect(function() {
    console.log(`[x1p] ShaperCalibration: timeout fired`);
    _setStatus(STATUS.TIMED_OUT);
});

function start(low, high) {
    _setStatus(STATUS.STARTING);
    _setCurrentRangeLow(low);
    _setCurrentRangeHigh(high);
    _setAxisAndFreq([null, null]);
    _setShaperData({"axes": { "x": { "points": {}, "summaries": [] }, "y": {"points": {}, "summaries": [] } }, "low": low, "high": high});
    _timeoutTimer.interval = TIMEOUT_FIRST_POINT_MS;
    _timeoutTimer.restart();
    _isFinishing = false;

    var gcode = X1Plus.GcodeGenerator.Vibration(low, high, 0 /* nozzle temp */, 0 /* bed temp */);
    if (X1Plus.emulating) {
        console.log("Would send gcode:");
        console.log(gcode);
        _startSynthetic();
    } else {
        X1Plus.sendGcode(gcode,0);
    }
}

function idle() {
    _setStatus(STATUS.IDLE);
}

function _calibrationFinished() {
    _timeoutTimer.stop();
    _setLastCalibrationTime(Math.floor(Date.now() / 1000));
    _saveShaperData();
    _setStatus(STATUS.DONE);
}

_DdsListener.gotDdsEvent.connect(function(topic, dstr) {
    if (status() != STATUS.STARTING && status() != STATUS.SWEEPING) {
        return;
    }
    const datum = JSON.parse(dstr);
    if (topic == "device/report/mc_print") {
        if (datum["command"] == "vc_data") {   
            var msg = datum["param"];
            
            var ax = currentAxis();
            if (msg.f == currentRangeLow()) {
                if (ax == null) {
                    ax = "y";
                } else if (ax == "y") {
                    ax = "x";
                } else {
                    console.log("[x1p] ShaperCalibration: saw low range too many times?");
                }
            }
            
            var _shaperData = shaperData();
            _shaperData.axes[ax].points[msg.f] = { "a": msg.a, "ph": msg.ph, "err": msg.err };
            _setShaperData(_shaperData); // trigger a changed event
            _setAxisAndFreq([ax, msg.f]); // atomically!

            _timeoutTimer.interval = TIMEOUT_POINT_MS;
            _timeoutTimer.restart();
            _setStatus(STATUS.SWEEPING);
        } else if (datum["command"] == "vc_enable") {
            _isFinishing = true;
            _finishVcParamCount = 0;
        } else if (datum["command"] == "vc_params" && _isFinishing) {
            var msg = datum["param"];
            
            var ax = _finishVcParamCount < 2 ? 'x' : 'y'; /* these get dumped out in the opposite order, for some reason */
            
            var _shaperData = shaperData();
            _shaperData.axes[ax].summaries.push({"wn": msg.wn, "ksi": msg.ksi, "pk": msg.pk, "l": msg.l, "h": msg.h});
            _setShaperData(_shaperData); // trigger a changed event
            
            _finishVcParamCount++;
            
            if (_finishVcParamCount == 4) {
                _calibrationFinished();
            }
        }
    }
});

/*** Calibration database persistent store ***/

var [_db, _dbChanged, _setDb ] = Binding.makeBinding(null);
function calibrationRuns() {
    return Object.keys(_db().runs).sort();
}

function _loadDatabase(noload) {
    let db = {};
    if (!noload) {
        db = X1Plus.loadJson(`/${_logPath}/${_fName}`) || {};
    }
    
    // Do we need to migrate it?
    let version = db.version || 0;
    let didMigrate = false;
    if (version > 1) {
        console.log("[x1p] ShaperCalibration: database version is too new; erasing :(");
        db = {};
        version = 0;
    }
    if (version == 0) {
        let olddb = db;
        console.log("[x1p] ShaperCalibration: migrating database version 0 to version 1");
        db = { version: 1, runs: {} };
        for (const k in olddb) {
            if (k == "dates") {
                continue;
            }
            
            const ent = olddb[k];
            const time = Math.floor(Date.parse(k) / 1000);
            const run = {
                time: time,
                axes: { x: { points: {}, summaries: [] }, y: { points: {}, summaries: [] } },
                low: ent.params[0],
                high: ent.params[1],
            };

            for (var i = 0; i < ent.f.length; i++) {
                run.axes.x.points[ent.f[i]] = { "a": ent.axis0[i] };
                run.axes.y.points[ent.f[i]] = { "a": ent.axis1[i] };
            }
            
            run.axes.y.summaries.push({wn: ent.wn[0], ksi: ent.ksi[0], pk: ent.pk[0]});
            run.axes.y.summaries.push({wn: ent.wn[1], ksi: ent.ksi[1], pk: ent.pk[1]});
            run.axes.x.summaries.push({wn: ent.wn[2], ksi: ent.ksi[2], pk: ent.pk[2]});
            run.axes.x.summaries.push({wn: ent.wn[3], ksi: ent.ksi[3], pk: ent.pk[3]});
            
            db.runs[time] = run;
        }
        didMigrate = true;
    }

    _setDb(db);
    if (didMigrate) {
        console.log(`[x1p] ShaperCalibration: migrations complete, writing out version ${db.version}`);
        _saveDatabase();
    }
}

function _saveDatabase() {
    /* XXX: we should write this atomically */
    console.log(`[x1p] ShaperCalibration: writing database`);
    X1Plus.saveJson(`/${_logPath}/${_fName}`, _db());
}

function _saveShaperData() {
    var entry = shaperData();
    entry.time = lastCalibrationTime();
    entry.temperature = X1Plus.emulating ? 25 : X1Plus.PrintManager.heaters.chamber.currentTemp;
    console.log(`[x1p] ShaperCalibration: saving new shaper result with ts ${entry.time}`);
    _db().runs[entry.time] = entry;
    _setDb(_db());
    _saveDatabase();
}

function getEntry(ts) {
    return _db().runs[ts];
}

function deleteEntry(ts) {
    if (_db().runs[ts]) {
        console.log(`[x1p] ShaperCalibration: deleting run with timestamp ${ts}`);
        delete _db().runs[ts];
        _setDb(_db());
        _saveDatabase();
    }
}

function deleteAll() {
    _db().runs = {};
    _setDb(_db());
    _saveDatabase();
}

/*** Synthetic data generation for emulation ***/

var _syntheticData = null;
var _syntheticDataIdx = 0
var _syntheticDataTimer = Binding.makeTimer();
_syntheticDataTimer.interval = 33;
_syntheticDataTimer.repeat = true;
_syntheticDataTimer.triggered.connect(function() {
    _DdsListener.gotDdsEvent("device/report/mc_print", JSON.stringify(_syntheticData[_syntheticDataIdx]));
    _syntheticDataIdx++;
    if (_syntheticDataIdx == _syntheticData.length) {
        _syntheticDataTimer.stop();
    }
});

function _startSynthetic() {
    _syntheticData = [];
    var axwns = [ Math.random() * 10 + 40, Math.random() * 10 + 40 ];
    var axpks = [ Math.random() * 3 + 20, Math.random() * 3 + 15 ];
    var half = (currentRangeLow() + currentRangeHigh()) / 2;
    for (var ax = 0; ax < 2; ax++) {
        for (var f = currentRangeLow(); f <= currentRangeHigh(); f++) {
            var a;
            if (f < axwns[ax]) {
                a = axpks[ax] - (Math.log10(axwns[ax]) - Math.log10(f)) * 1.5 * (axpks[ax] / Math.log10(axwns[ax]));
            } else {
                a = axpks[ax] - (Math.log10(f) - Math.log10(axwns[ax])) * 40; /* 40 dB per decade rolloff */
            }
            a += Math.random() * 2;
            _syntheticData.push({ command: "vc_data", param: { "f": f, "a": a, "ph": Math.random() * Math.PI * 2 - Math.PI, "err": 0 } });
            if (f == half && ax != 1 /* ??? */) {
                _syntheticData.push({ command: "vc_params", param: { "wn": axwns[ax], "ksi": 0.1234, "pk": axwns[ax], "l": currentRangeLow(), "h": half } });
            }
        }
        _syntheticData.push({ command: "vc_params", param: { "wn": 0, "ksi": 0, "pk": half, "l": half, "h": currentRangeHigh() } });
    }
    _syntheticData.push({ command: "vc_enable" });
    _syntheticData.push({ command: "vc_params", param: { "wn": axwns[1], "ksi": 0.1234, "pk": axpks[1], "l": 1, "h": 2 } });
    _syntheticData.push({ command: "vc_params", param: { "wn": 0, "ksi": 0.2345, "pk": axpks[1], "l": 3, "h": 4 } });
    _syntheticData.push({ command: "vc_params", param: { "wn": axwns[0], "ksi": 0.1234, "pk": axpks[0], "l": 5, "h": 6 } });
    _syntheticData.push({ command: "vc_params", param: { "wn": 0, "ksi": 0.2345, "pk": axpks[0], "l": 7, "h": 8 } });
    
    _syntheticDataIdx = 0;
    _syntheticDataTimer.start();
}
