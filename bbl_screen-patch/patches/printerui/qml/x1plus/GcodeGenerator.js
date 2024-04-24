.pragma library
.import X1PlusNative 1.0 as JSX1PlusNative

var X1Plus = null;
var _X1PlusNative = JSX1PlusNative.X1PlusNative;

function createGcode(command, params = {}) {
    let gcode = `${command}`;
    for (const [key, value] of Object.entries(params)) {
        if (value !== '') {
            gcode += ` ${key}${value}`;
        }
    }
    return `${gcode}\n`;
}


/** 
 * Bambu placeholders for gcode
 * These can be used in conditional expressions with Gcode to write fairly complex macros
 * More placeholders and info about placeholders: 
 * https://wiki.bambulab.com/en/software/bambu-studio/placeholder-list
*/
const placeholders = {
    layer_num: () => "{layer_num}",
    layer_z: (dz) => `{layer_z + ${dz}}`,
    total_layer_count: () => "[total_layer_count]",
    old_retract_length: () => "[old_retract_length]",
    new_retract_length: () => "[new_retract_length]",
    old_filament_temp: () => "[old_filament_temp]",
    new_filament_temp: () => "[new_filament_temp]",
    filament_type: (idx) => `{filament_type[${idx}]}`,
    x_after_toolchange: () => "[x_after_toolchange]",
    y_after_toolchange: () => "[y_after_toolchange]",
    z_after_toolchange: () => "[z_after_toolchange]",
    old_filament_e_feedrate: () => "{old_filament_e_feedrate}",
    new_filament_e_feedrate: () => "{new_filament_e_feedrate}",
    bed_temperature: (target) => `{bed_temperature[${target}]}`,
    bed_temperature_initial_layer_single: () => "{bed_temperature_initial_layer_single}",
    bed_temperature_initial_layer: (target) => `{bed_temperature_initial_layer[${target}]}`,
    nozzle_temperature_initial_layer: (idx) => `{nozzle_temperature_initial_layer[${idx}]}`,
    flush_length: (idx) => `{flush_length_${idx}}`,
    filament_extruder_id: () =>  `{filament_extruder_id}`,

}


/** 
 * skew compensation 
 * usage: gcode = GcodeGenerator.M1005.xy(84.99, 84.98)
 * or
 * gcode = GcodeGenerator.M1005.i(0.00015)
*/
var M1005 = { 
    xy: (x,y) => `M1005 X${x} Y${y}\n`,
    i: (i) => `M1005 I${i}\n`,
    save: () => M500()
}


/* update timeline */
function M73(val1, val2) {
    return `M73 P${val1} R${val2}\n`;
}


/* homing */
var G28 = { 
    xyz: () => {
        return `G28\n`;
    },
    z_low_precision: () => {
        return `G28 Z P0\n`;
    },
    z_low_precision_heated: (temp) => {
        return `G28 Z P0 T${temp}\n`;
    },
    xy: () => {
        return `G28 X\n`;
    }
}

/* endstops */
function M211({s='', x = '', y = '', z = ''}) {
    return createGcode('M211', {S:s, X: x, Y: y, Z: z});
}

/* toggle mesh compensation */
function G292(enabled = 1) {
    return `G29.2 S${enabled}\n`;
}

/* bed mesh calibration */
function G29(){
    return "G29\n";
}
/* absolute coords */
function G90() {
    return "G90\n";
}

/* relative coords */
function G91() {
    return "G91\n";
}
/* reset extruder position */
function G92() {
    return "G92 E0\n";
}


/* heat bed + wait */
function M140(temp) {
    return createGcode('M140', {S: temp});
}

/* heat bed */
function M190(temp) {
    return createGcode('M190', {S: temp});}

/* heat nozzle + wait */
function M109(temp) {
    return createGcode('M109', {S: temp});
}
/* heat nozzle */
function M104(temp) {
    return createGcode('M104', {S: temp});
}

/* save settings */
function M500() {
    return 'M500\n';
}

/* stepper current */
function M17(x, y, z) {
    return createGcode('M17', {X: x, Y: y, Z: z});
}

/* toggle vibration compensation */
function M975(enabled = true) {
    const status = enabled ? '1' : '0';
    return `M975 S${status}\n`;
}

/* k value */
function M900(k, l, m) {
    return createGcode('M900', {K: k, L: l, M: m});
}

/* motion control - no extrusion */
function G0({ x = '', y = '', z = '', accel = '' }) {
    return createGcode('G0', { X: x, Y: y, Z: z, F: accel });
}
/* motion control with extrusion */
function G1({ x = '', y = '', z = '', e = '', accel = '' }) {
    return createGcode('G1', { X: x, Y: y, Z: z, E: e, F: accel });
}
/* arc */
function G2({ z=0.6, i = 0.5, j = 0,p = 1, accel = 300 }) {
    return createGcode('G2', {Z:z, I: i, J: j,P: p, F: accel });
}

/* claim_action function */
var M1002 = { 
    gcode_claim_action: (code) => `M1002 gcode_claim_action ${code}\n `,
    judge_flag: (code) => `M1002 judge_flag ${code}\n `,
    set_gcode_claim_speed_level: (code) => `M1002 set_gcode_claim_speed_level ${code}\n `,
}

/* fast sweep */
function M9703(axis = 0, a = 7, b = 30, c = 80, h = 0, k = 0) 
{
    return h > 0 ? `M970.3 Q${axis} A${a} B${b} C${c} H${h} K${k}\n` : `M970.3 Q${axis} A${a} B${b} C${c} K${k}\n`;
}
/* frequency sweep */
function M970({axis, a, f_low, f_high, h, k})
{
    return h ? `M970 Q${axis} A${a} B${f_low} C${f_high} H${h} K${k}\n`
             : `M970 Q${axis} A${a} B${f_low} C${f_high} K${k}\n`;
}
/* curve fitting for vibration compensation */
function M974(axis = 0) {
    return `M974 Q${axis} S2 P0\n`;
}

/* pause */
var M400 = {
    pause: (t) => `M400 S${t}\n`, //delay _ seconds
    M400: () => "M400\n", //wait for last gcode command to finish
    pause_user_input: () => "M400 U1\n", //pause until user presses "Resume"
}

/* pause */
function G4(sec = 90) 
{
    let gcode = '';
    const fullCycles = Math.floor(sec / 90);
    const remainder = sec % 90;

    for (let i = 0; i < fullCycles; i++) {
        gcode += 'G4 S90\n';
    }
    if (remainder > 0) {
        gcode += `G4 S${remainder}\n`;
    }
    return gcode;
}

/* set jerk limits */
function M205({x , y , z , e }) 
{
    return createGcode('M205', {X: x, Y: y, Z: z, E: e});
}

/* disable motor noise cancellation */
function M9822()
{
    return "M982.2 C0\n M982.2 C1\n";
}


/* fan control, val = 0 to 255 */
var M106 = {
    part: (val) => `M106 P1 S${val}\n`,
    aux: (val) => `M106 P2 S${val}\n`,
    chamber: (val) => `M106 P3 S${val}\n`,
}

/* set feed rate (default = 100%) */
function M220(s=100)
{
    return `M220 S${s}\n`;
}

 /* set flow rate (default = 100%) */
function M221(s)
{
    return `M221 S${s}\n`;
}

 /* set acceleration limit (mm/s^2), e.g M204 S9000 */
function M204(s)
{
    return `M204 S${s}\n`;
}

 /**
  * LED controls 
  * 0 = off, 1 = on 
 */
var M960 = {
    laser_vertical: (val) => {
        return `M960 S1 P${val}\n`;
    },
    laser_horizontal: (val) => {
        return `M960 S2 P${val}\n`;
    },
    nozzle: (val) => {
        return `M960 S4 P${val}\n`;
    },
    toolhead: (val) => {
        return `M960 S5 P${val}\n`;
    },
    all: (val) => {
        return `M960 S0 P${val}\n`;
    }  
}

/* nozzle camera controls */
var M973 = {
    off: () => {
        return `M973 S4\n`;
    },
    on: () => {
        return `M973 S3 P1\n`;
    },
    autoexpose: () => {
        return `M973 S1\n`;
    },
    expose: (image,val) => {
        return `M973 S${image} P${val}\n`;
    },
    capture: (image,val) => {
        return `M971 S${image} P${val}\n`;
    }  
}

/* set maximum acceleration for Z axis (units mm/s^2) */
function M201(z){
    return `M201 Z${z}\n`;
}

/**
 * AMS gcode - still need to figure out how it works
 * Missing M620, M620.1, M624, and M625
*/
function  M622(j){
    return `M622 J${j}\n`;
}
function  M623(){
    return 'M623\n';
}

/* set extruder to relative */
function  M83(){ 
    return 'M83\n';
}

/* disable steppers */
function  M84(){ 
    return 'M84\n';
}

/* toggle filament runout detection */
function M412(s){
    return `M412 S${s}\n`;
}

/* enable/disable cold extrusion  */
function M302(p){
    return `M302 S70 P${p}\n`;
}

/* set z offset */
function G291(z_trim=0) {
//+0.00 default; -0.04 for textured PEI
    return `G29.1 Z{${z_trim}}\n`;
}

/* reset acceleration multiplier*/
function M2012() {
    return `M201.2 K1.0\n`;
}

/** unknown Bambu shaper gcode from 
/* auto_cali_for_usr_param.gcode 
*/
function G921() {
    return `G92.1\n`;
}

/* Vibration compensation calibration */
function Vibration(freq1, freq2, nozzleTemp, bedTemp) {
    let mid = Math.floor((freq2 - freq1) * 0.5);
    let gcode = [];
    gcode.push(M1002.gcode_claim_action(13))
    if (nozzleTemp > 0) {
        gcode.push(M109(nozzleTemp));
    }
    if (bedTemp > 0) {
        gcode.push(M140(bedTemp));
    }

    gcode.push(
        M73(0, 3),
        M201(100),
        G90(),
        M400.pause(1),
        M17(1.2, 1.2, 0.75),
        G28.xyz(),
        G921(),
        G0({x: 128, y: 128, z: 5, accel: 2400}),
        M201(1000),
        M400.pause(1),
        M1002.gcode_claim_action(3),
        M970({axis: 1, a: 7, f_low: freq1, f_high: mid, k: 0}),
        M73(25, 3),
        M970({axis: 1, a: 7, f_low: mid + 1, f_high: freq2, k: 1}),
        M73(50, 2),
        M974(1),
        M970({axis: 0, a: 9, f_low: freq1, f_high: mid, h: 20, k: 0}),
        M73(75, 1),
        M970({axis: 0, a: 9, f_low: mid + 1, f_high: freq2, k: 1}),
        M73(100, 0),
        M974(0),
        M500(),
        M975(true),
        G0({x: 65, y: 260, z: 10, accel: 1800}),
        M400.pause(1),
        M140(0),
        M109(0),
        M1002.gcode_claim_action(0)
    );

    return gcode.join('');
}


/* Semi-automate cold pulls */
const ColdPull = {
    prepare: () => [
        G28.xy(), // xy home
        G91(),
        G0({z: 30, accel: 100}),
        M83(), // relative extrusion
        M302(1) // enable cold extrusion
    ].join(''),

    load: (load_temp) => [
        G1({e: 10, accel: 100}), // extrude
        M109(load_temp)
    ].join(''),

    flush: (flush_temp, second_flush_temp) => [
        G1({e: 60, accel: 100}), // fill the nozzle and flush a very small amount
        M106.aux(255), // fans on
        M106.part(255),
        M109(flush_temp), // lower temp
        G1({e: 10, accel: 100}), // flush a small amount at a lower temp
        M104(second_flush_temp) // lower temp
    ].join(''),

    pull: (pull_temp) => [
        M109(pull_temp),
        G1({e: -100, accel: 1200}) // extrude while the user pulls
    ].join(''),

    exit: () => [
        M104(0),
        M1002.gcode_claim_action(0),
        M106.aux(0),
        M106.part(0),
        M84() // disable steppers
    ].join('')
};

/* "Convective preheat" using heatbed and fans to warm the chamber */
const Preheat = {
    home: () => [
        G28.z_low_precision(),
        G91(), // relative
        G0({z: 5, accel: 1200}) // move toolhead close to bed
    ].join(''),

    on: (temp) => [
        M140(temp), // heater on
        M106.aux(255), // fans on
        M106.part(255)
    ].join(''),

    off: () => [
        M140(0), // heater off
        M106.aux(0), // fans off
        M106.part(0),
        G90() // absolute
    ].join('')
};

/* Tramming Gcode */
const Tramming = {
    exit: () => [
        M1002.gcode_claim_action(254),
        G1({x: 128, y: 128, z: 1}),
        M400.M400(),
        M1002.gcode_claim_action(0),
    ].join(''),

    prepare: () => [
        M1002.gcode_claim_action(254),
        M17(1.2, 1.2, 0.75),
        G90(),
        M83(),
        G28.xyz(),
        G1({x: 128, y: 128, z: 1}),
        G292(0),
        M1002.gcode_claim_action(1),
    ].join(''),

    rear_center: () => [
        M1002.gcode_claim_action(254),
        G1({x: 134.8, y: 242.8, z: 0.4, accel: 3600}),
        M400.M400(),
        M1002.gcode_claim_action(1),
    ].join(''),

    front_left: () => [
        M1002.gcode_claim_action(254),
        G1({x: 33.2, y: 13.2, z: 0.4, accel: 3600}),
        M400.M400(),
        M1002.gcode_claim_action(1),
    ].join(''),

    front_right: () => [
        M1002.gcode_claim_action(254),
        G1({x: 222.8, y: 13.2, z: 0.4, accel: 3600}),
        M400.M400(),
        M1002.gcode_claim_action(1),
    ].join('')
};


/* Bambu print speed parameters */
var speed_presets = {
    "Silent": { speed: 50, speed_fraction: 2, accelerationMagnitude: 0.3, feedRate: 0.7 , level: 4},
    "Normal": { speed: 100, speed_fraction: 1, accelerationMagnitude: 1, feedRate: 1, level: 5 },
    "Sport": { speed: 125, speed_fraction: 0.8, accelerationMagnitude: 1.4, feedRate: 1.4, level: 6 },
    "Ludicrous": { speed: 166, speed_fraction: 0.6, accelerationMagnitude: 1.6, feedRate: 2, level: 7 }
};

/** 
 * Interpolation of Bambu print speed parameters. Details about this process at here:
 * https://github.com/jphannifan/x1plus-testing/blob/main/BL-speed-adjust.md
 * We can modify this readme and turn it into Wiki content.
 * */
var speed_interpolation = {
    speed_fraction: (speedPercentage) => { return Math.floor(10000/speedPercentage)/100},
    acceleration_magnitude: (speedFraction) => {return Math.exp((speedFraction - 1.0191) / -0.814)},
    feed_rate: (speedPercentage) => {return (0.00006426)*speedPercentage ** 2 + (-0.002484)*speedPercentage + 0.654},
    level: (accelerationMagnitude) => {return (1.549 * accelerationMagnitude ** 2 - 0.7032 * accelerationMagnitude + 4.0834)}
}

/**
 * Print speed Gcode - M204.2 (acceleration magnitude), M220 (feed rate), and 
 * M73.2 (time remaining parameter)
 * 
 * Usage: Input a string ["Silent", "Normal", "Sport", "Ludicrous"] to generate
 * Gcode for OEM speed profiles. Input an integer between 30 and 180 to generate
 * Gcode with interpolated parameters.
 */
function printSpeed(inputSpeed) {
    let config;
    if (typeof inputSpeed === 'string') {
        config = speed_presets[inputSpeed];
        if (!config) {
            return "";
        }
    } else if (typeof inputSpeed === 'number') {
        if (inputSpeed < 30 || inputSpeed > 180) {
            inputSpeed = 100;
        }
        var speedFraction = speed_interpolation.speed_fraction(inputSpeed);
        var accelerationMagnitude = speed_interpolation.acceleration_magnitude(speedFraction);
        var feedRate = speed_interpolation.feed_rate(inputSpeed);
        var level = speed_interpolation.level(accelerationMagnitude);
        config = {
            speed_fraction: speedFraction,
            accelerationMagnitude: accelerationMagnitude,
            feedRate: feedRate,
            level: level > 7 ? 7 : level
        };
    } else {
        return "";
    }
    return [
        `M204.2 K${config.accelerationMagnitude.toFixed(2)}`, // Set acceleration magnitude
        `M220 K${config.feedRate.toFixed(2)}`, // Set feed rate
        `M73.2 R${config.speed_fraction}`, //time remaining parameter
        M1002.set_gcode_claim_speed_level(Math.round(config.level)) // Set speed level
    ].join("\n") + "\n";
}
