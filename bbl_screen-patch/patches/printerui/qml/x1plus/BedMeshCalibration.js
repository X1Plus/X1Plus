.pragma library
.import DdsListener 1.0 as JSDdsListener
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;

var _DdsListener = JSDdsListener.DdsListener;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

var _logPath;
var _fName = 'mesh_data.json';

var STATUS = {
    IDLE: 0,
    STARTING: 1,
    PROBING: 2,
    TIMED_OUT: 3,
    DONE: 4
};
var N_MESH_POINTS = 36;

var [status, statusChanged, _setStatus] = Binding.makeBinding(STATUS.IDLE);
var [mesh, meshChanged, _setMesh] = Binding.makeBinding(null);
var [pointCount, pointCountChanged, _setPointCount] = Binding.makeBinding(0);
var [lastX, lastXChanged, _setLastX] = Binding.makeBinding(null);
var [lastY, lastYChanged, _setLastY] = Binding.makeBinding(null);
var [lastZ, lastZChanged, _setLastZ] = Binding.makeBinding(null);
var [lastCalibrationTime, lastCalibrationTimeChanged, _setLastCalibrationTime] = Binding.makeBinding(null);
var isActive = function() { return status() == STATUS.STARTING || status() == STATUS.PROBING; };

function awaken() {
    _logPath = `${X1Plus.printerConfigDir}/logs`;
    _X1PlusNative.system("mkdir -p " + _X1PlusNative.getenv("EMULATION_WORKAROUNDS") + _logPath);
    console.log(`[x1p] BedMeshCalibration: logPath is ${_logPath}`);
    try {
        _loadDatabase();
    } catch (e) {
        console.log("[x1p] BedMeshCalibration: failed to load database; erasing");
        _loadDatabase(true);
    }
}

/*** Calibration capture ***/

const TIMEOUT_FIRST_POINT_MS = 90000;
const TIMEOUT_POINT_MS = 15000;

var _timeoutTimer = Binding.makeTimer();
_timeoutTimer.repeat = false;
_timeoutTimer.triggered.connect(function() {
    console.log(`[x1p] BedMeshCalibration: timeout fired on point ${pointCount()}`);
    _setStatus(STATUS.TIMED_OUT);
});

function start() {
    _setStatus(STATUS.STARTING);
    _setPointCount(0);
    _setMesh({});
    _timeoutTimer.interval = TIMEOUT_FIRST_POINT_MS;
    _timeoutTimer.restart();

    if (X1Plus.emulating) {
        _startSynthetic();
    } else {
        X1Plus.PrintManager.calibrate(2);
    }
}

function idle() {
    _setStatus(STATUS.IDLE);
}

function _calibrationFinished() {
    _timeoutTimer.stop();
    _setLastCalibrationTime(Math.floor(Date.now() / 1000));
    _saveMesh();
    _setStatus(STATUS.DONE);
}

_DdsListener.gotDdsEvent.connect(function(topic, dstr) {
    if (status() != STATUS.STARTING && status() != STATUS.PROBING) {
        return;
    }
    if (topic == "device/report/mc_print") {
        const datum = JSON.parse(dstr);
        if (datum["command"] == "mesh_data") {
            var msg = datum["param"];
            
            if (msg["x"] == null)
                return;
            var x = parseFloat(msg["x"]);
            var y = parseFloat(msg["y"]);
            var z = parseFloat(msg["z"]);
            
            var _mesh = mesh();
            if (!_mesh[y])
                _mesh[y] = {};
            _mesh[y][x] = z;
            _setMesh(_mesh); // trigger a changed event for the mesh

            _timeoutTimer.interval = TIMEOUT_POINT_MS;
            _timeoutTimer.restart();
            _setStatus(STATUS.PROBING);

            _setLastX(x);
            _setLastY(y);
            _setLastZ(z);
            _setPointCount(pointCount() + 1);
            if (pointCount() == N_MESH_POINTS) {
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
        console.log("[x1p] BedMeshCalibration: database version is too new; erasing :(");
        db = {};
        version = 0;
    }
    if (version == 0) {
        let olddb = db;
        console.log("[x1p] BedMeshCalibration: migrating database version 0 to version 1");
        db = { version: 1, runs: {} };
        for (const k in olddb) {
            if (k == "dates") {
                continue;
            }
            
            const ent = olddb[k];
            const time = Math.floor(Date.parse(k) / 1000);
            const mesh = {};
            for (const y in ent) {
                if (isNaN(parseFloat(y))) {
                    continue;
                }
                mesh[y] = ent[y];
                
            }
            const temp = parseInt(ent.temp);
            const tilt = X1Plus.MeshCalcs.bedMetrics(mesh);
            
            db.runs[time] = {
                time: time,
                mesh: mesh,
                temperature: temp,
                bedMetrics: tilt
            };
        }
        didMigrate = true;
    }

    _setDb(db);
    if (didMigrate) {
        console.log(`[x1p] BedMeshCalibration: migrations complete, writing out version ${db.version}`);
        _saveDatabase();
    }
}

function _saveDatabase() {
    /* XXX: we should write this atomically */
    console.log(`[x1p] BedMeshCalibration: writing database`);
    X1Plus.saveJson(`/${_logPath}/${_fName}`, _db());
}

function _saveMesh() {
    var entry = {
        time: lastCalibrationTime(),
        mesh: mesh(),
        temperature: X1Plus.emulating ? 100 : X1Plus.PrintManager.heaters.heatbed.currentTemp,
        bedMetrics: X1Plus.MeshCalcs.bedMetrics(mesh()),
    };
    console.log(`[x1p] BedMeshCalibration: saving new mesh with ts ${entry.time}`);
    _db().runs[entry.time] = entry;
    _setDb(_db());
    _saveDatabase();
}

function getEntry(ts) {
    return _db().runs[ts];
}

function deleteEntry(ts) {
    if (_db().runs[ts]) {
        console.log(`[x1p] BedMeshCalibration: deleting run with timestamp ${ts}`);
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
_syntheticDataTimer.interval = 100;
_syntheticDataTimer.repeat = true;
_syntheticDataTimer.triggered.connect(function() {
    _DdsListener.gotDdsEvent("device/report/mc_print", JSON.stringify(_syntheticData[_syntheticDataIdx]));
    _syntheticDataIdx++;
    if (_syntheticDataIdx == _syntheticData.length) {
        _syntheticDataTimer.stop();
    }
});

function _startSynthetic() {
    var xs = ["25", "66.2", "107.4", "148.6", "189.8", "231"];
    var ys = ["25", "67.2", "109.4", "151.6", "193.8", "236"];

    _syntheticData = [];
    for (var i = 0; i < ys.length; i++)
        for (var j = 0; j < xs.length; j++)
            _syntheticData.push({"command": "mesh_data",  "param": {x: xs[j], y: ys[i], z:(Math.random() * 0.5).toFixed(2)}});
    _syntheticDataIdx = 0;
    _syntheticDataTimer.start();
}

/* At some point, this may make a return:

    function generateEmuData(entries) { //for emulation
        const meshData = { dates: [] };
        const yValues = [25, 236, 67.2, 109.4, 151.6, 193.8];
        const xValues = [25, 231, 66.2, 107.4, 148.6, 189.8];
        for (let i = 0; i < entries; i++) {
            const timestamp = new Date(Date.now() - Math.floor(Math.random() * 365 * 24 * 60 * 60 * 1000));
            const formattedTimestamp = timestamp.toLocaleString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            });
            meshData.dates.push(formattedTimestamp);
            meshData[formattedTimestamp] = {};

            yValues.forEach(y => {
                meshData[formattedTimestamp][y] = {};
                xValues.forEach(x => {
                    meshData[formattedTimestamp][y][x] = parseFloat((Math.random() * 2 - 1).toFixed(3));
                });
            });

            meshData[formattedTimestamp]['temp'] = Math.floor(Math.random() * (70 - 20 + 1)) + 20;
            meshData[formattedTimestamp]['tiltCalcs'] = {
                xTilt: (Math.random() * 0.1).toFixed(2),
                yTilt: (Math.random() * 0.1).toFixed(2),
                peak: (Math.random() * 0.1).toFixed(2)
            };
        }
        return meshData;
    }

*/