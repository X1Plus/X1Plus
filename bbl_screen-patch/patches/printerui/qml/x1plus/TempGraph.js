.pragma library
.import DdsListener 1.0 as JSDdsListener
.import X1PlusNative 1.0 as JSX1PlusNative
.import "Binding.js" as Binding

var X1Plus = null;

const N_SAMPLES = 15 * 60;

/* sample format is [ nozzletemp, nozzleset, bedtemp, bedset, chambertemp ] */
var [samples, onSamplesChanged, _setSamples] = Binding.makeBinding([]);

var _sampleTimer = Binding.makeTimer();
_sampleTimer.repeat = true;
_sampleTimer.interval = 1000;
_sampleTimer.triggered.connect(function() {
    var _samples = samples();
    if (_samples.length == N_SAMPLES) {
        _samples.shift();
    }
    _samples.push([
        X1Plus.PrintManager.heaters.hotend.currentTemp,
        X1Plus.PrintManager.heaters.hotend.targetTemp,
        X1Plus.PrintManager.heaters.heatbed.currentTemp,
        X1Plus.PrintManager.heaters.heatbed.targetTemp,
        X1Plus.PrintManager.heaters.chamber.currentTemp,
    ]);
    X1Plus.saveJson("/tmp/temperaturelog.json", _samples);
    _setSamples(_samples);
});

function awaken() {
    var loaded = X1Plus.loadJson("/tmp/temperaturelog.json");
    if (loaded)
        _setSamples(loaded);
    _sampleTimer.start();
}
