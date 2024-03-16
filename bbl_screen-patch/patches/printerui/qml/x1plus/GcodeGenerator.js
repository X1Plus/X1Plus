const MACROS = {
    VIBRATION_COMP: 0,
    BED_LEVEL: 1,
    NOZZLE_CAM_PREVIEW: 2,
    TRAMMING: 3
};

const TRAMMING_STEP = {
    EXIT: 0,
    PREPARE: 1,
    REAR_CENTER: 2,
    FRONT_LEFT: 3,
    FRONT_RIGHT: 4
};

const OV2740 = {
    OFF: 0,
    ON: 1,
    AUTOEXPOSE: 2,
    EXPOSE: 3,
    CAPTURE: 4
}
const LEDS = {
    LASER_VERTICAL: 0,
    LASER_HORIZONTAL: 1,
    LED_NOZZLE: 2,
    LED_TOOLHEAD: 3,
    ALL_LEDS: 4
}
const HOMING = {
    XYZ: 0,
    Z_LOW_PRECISION: 1,
    Z_LOW_PRECISION_HOTEND_ON: 2,
    XY: 3
}
const SPEED_LEVELS = {
    SILENT: 4,
    NORMAL: 5,
    SPORT: 6,
    LUDA: 7
}
const FANS = {
    PART_FAN: 1,
    AUX_FAN: 2,
    CHAMBER_FAN:3
}


function createGcode(command, params = {}) {
    let gcode = `${command}`;
    for (const [key, value] of Object.entries(params)) {
        if (value !== '') {
            gcode += ` ${key}${value}`;
        }
    }
    return `${gcode}\n`;
}
function macros_nozzlecam() {
    let gcode = G28(0);
    gcode += G0({x: 240, y: 90, z: 8, accel: 1200});
    gcode += M960(LEDS.LED_NOZZLE, 1);
    gcode += M973(OV2740.ON);
    gcode += M973(OV2740.AUTOEXPOSE);
    gcode += 'M400 P100 \n';
    gcode += M973(OV2740.CAPTURE, 1, 1);
    gcode += M960(LEDS.LED_NOZZLE, 0);
    gcode += M973(OV2740.OFF);
    return gcode;
}
function macros_tramming(step) {
    let gcode = M1002({action_code:254,action:0});
    switch (step) {
        case TRAMMING_STEP.EXIT:
            gcode += G1({x: 128, y: 128, z: 1});
            gcode += M400(0);
            break;
        case TRAMMING_STEP.PREPARE:
            gcode += M17(1.2, 1.2, 0.75);
            gcode += G90();
            gcode += M83();
            gcode += G28(0);
            gcode += G1({x: 128, y: 128, z: 1});
            gcode += G292(0);
            break;
        case TRAMMING_STEP.REAR_CENTER:
            gcode += G1({x: 134.8, y: 242.8, z: 0.4, accel: 3600});
            gcode += M400(0);
            break;
        case TRAMMING_STEP.FRONT_LEFT:
            gcode += G1({x: 33.2, y: 13.2, z: 0.4, accel: 3600});
            gcode += M400(0);
            break;
        case TRAMMING_STEP.FRONT_RIGHT:
            gcode += G1({x: 222.8, y: 13.2, z: 0.4, accel: 3600});
            gcode += M400(0);
            break;
    }
    gcode += M1002({action_code:1,action:0});
    return gcode;
}
function macros_vibrationCompensation(f1,f3,nozzleTemp,bedTemp) {
    let f2 = Math.floor((f3-f1)*0.5); //midpoint
    
    let header = M1002({action_code:13,action:0});
    let footer = M1002({action_code:0,action:0});
    if (nozzleTemp>0 && nozzleTemp <= 300){
        header += M109(nozzleTemp);
        footer += M109(0);
    }
    if (bedTemp>0 && bedTemp <= 300){
        header += M140(bedTemp,true);
        footer += zzzM140(0,false);
    }

    let gcode = M73(0,3); // update timeline
    gcode += M201(100); // set Z max accel
    gcode += G90(); // absolute coords
    gcode += M400(1); // pause
    gcode += M17(1.2, 1.2, 0.75); // stepper current Z=0.75
    gcode += M201(1000); // set Z max accel
    gcode += G28(HOMING.XYZ); // home
    gcode += G92_1(); // unknown Bambu shaper code
    gcode += G0({x: 128, y: 128, z: 5, accel: 2400}); // move
    gcode += header;
    gcode += M400(1) // pause

    //SWEEP

    gcode += M1002({action_code:3,action:0});
    gcode += M970({axis: 1, a: 7, f_low: f1    , f_high: f2, k: 0}); // do the sweep
    gcode += M73(25,3);
    gcode += M970({axis: 1, a: 7, f_low: f2 + 1, f_high: f3, k: 1});
    gcode += M73(50,2);
    gcode += M974(1);
    gcode += M970({axis: 0, a: 9, f_low: f1    , f_high: f2, h: 20, k: 0});
    gcode += M73(75,1);
    gcode += M970({axis: 0, a: 9, f_low: f2 + 1, f_high: f3, k: 1});
    gcode += M73(100,0);
    gcode += M974(0);
    gcode += M500(); // save settings
    gcode += M975(true); // enable shaper
    
    gcode += footer;
    gcode += G0({x: 65, y: 260, z: 10, accel: 1800});

    gcode += M400(1);
    return gcode;
}
function macros_ABL() {
    let gcode = M1002({action_code:0,action:1});
    gcode += M622(1);
    gcode += M1002({action_code:1,action:0});
    gcode += G29();
    gcode += M400(0);
    gcode += M500();
    gcode += M623();
    return gcode;
}


/* update timeline */
function M73(val1, val2) {
    return `M73 P${val1} R${val2}\n`;
}

/* homing */
function G28(type = 0, nozzle_temp = 0) {
    switch (type) {
        case HOMING.XYZ: return 'G28\n';
        case HOMING.Z_LOW_PRECISION: return 'G28 Z P0\n';
        case HOMING.Z_LOW_PRECISION_HOTEND_ON: return `G28 Z P0 T${nozzle_temp}\n`;
        case HOMING.XY: return 'G28 X\n';
        default: return 'G28\n';
    }
}
/* endstops */
function M211({ x = '', y = '', z = ''}) {
    return this.createGcode('M211', { X: x, Y: y, Z: z});
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

/* unknown: used in Bambu shaper calibration */
function G92_1() {
    return "G92.1\n";
}

/* heat bed */
function M140(temp, wait = false) {
    return wait ? this.createGcode('M140', {S: temp}) + this.createGcode('M190', {S: temp}) : this.createGcode('M140', {S: temp});
}

/* heat nozzle */
function M109(temp) {
    return this.createGcode('M109', {S: temp});
}

/* save settings */
function M500() {
    return 'M500\n';
}

/* stepper current */
function M17(x, y, z) {
    return this.createGcode('M17', {X: x, Y: y, Z: z});
}

/* toggle vibration compensation */
function M975(enabled = true) {
    const status = enabled ? '1' : '0';
    return `M975 S${status}\n`;
}

/* k value */
function M900(k, l, m) {
    return this.createGcode('M900', {K: k, L: l, M: m});
}

/* print speed level */
function M1009(level) {
    const p1 = [0.3, 1, 1.4, 1.6];
    const p2 = [0.7, 1, 1.4, 2.0];
    const p3 = [2, 1, 0.8, 0.6];
    return `M1009 L1 O1 M204.2 K${p1[level - 4]} M220 K${p2[level - 4]} M73.2 R${p3[level - 4]} M1002 ${level}\n`;
}
/* motion control */
function G0({ x = '', y = '', z = '', accel = '' }) {
    return this.createGcode('G0', { X: x, Y: y, Z: z, F: accel });
}

function G1({ x = '', y = '', z = '', e = '', accel = '' }) {
    return this.createGcode('G1', { X: x, Y: y, Z: z, E: e, F: accel });
}
/* claim action and judge flag */
function M1002({action_code, action = 0}) {
    const judge_flags = [
        "g29_before_print_flag",
        "xy_mech_mode_sweep_flag",
        "do_micro_lidar_cali_flag",
        "timelapse_record_flag"
    ];
    const claim_actions = [
        "0 Clear screen of messages",
        "1 Auto bed levelling",
        "2 Heatbed preheating",
        "3 Sweeping XY mech mode",
        "4 Changing filament",
        "5 M400 pause",
        "6 Paused due to filament runout",
        "7 Heating hotend",
        "8 Calibrating extrusion",
        "9 Scanning bed surface",
        "10 Inspecting first layer",
        "11 Identifying build plate type",
        "12 Calibrating Micro Lidar",
        "13 Homing toolhead",
        "14 Cleaning nozzle tip",
        "15 Checking extruder temperature",
        "16 Paused by the user",
        "17 Pause due to the falling off of the tool head’s front cover",
        "18 Calibrating the micro lidar",
        "19 Calibrating extruder flow",
        "20 Paused due to nozzle temperature malfunction",
        "21 Paused due to heat bed temperature malfunction"
    ];
    const actions = {
        0: () => `M1002 gcode_claim_action : ${action_code} \n `,
        1: () => `M1002 judge_flag : ${action_code} \n `
    };
    return (actions[action] || (() => ''))();
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
function M974(axis = 0) 
{
    return `M974 Q${axis} S2 P0\n`;
}

function G292(enabled = 1) /* toggle abl */
{
    return `G29.2 S${enabled}\n`;
}

function M400(sec = 0) /* pause */
{
    return sec > 0 ? `M400 S${sec}\n` : `M400\n`;
}

function G4(sec = 90) /* pause */
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

function M205({x , y , z , e })
{
    return createGcode('M205', {X: x, Y: y, Z: z, E: e});
}
function M9822() /* disable motor noise cancellation */
{
    return "M982.2 C0\n M982.2 C1\n";
}

function  M106(fan = FANS.PART_FAN, speed = 0) /* fan control */
{
    return `M106 P${fan} S${speed}\n`;
}

function M220() /* reset flow rate */
{
    return `M220 S100\n`;
}


function M221({x = -1,y = -1,z = -1}) 
{
    if (x == -1 && y == -1 && z == -1){
        return "M221 S100\n"; /* reset flow rate */
    } else {
        return createGcode('M221', { X:x,Y:y,Z:z});/* jerk limits */
    }
}


function M960({type, val}){ /* led controls */
    var gcode;
    if (type == LEDS.LASER_VERTICAL) gcode = `M960 S1 P${val}`;
    if (type == LEDS.LASER_HORIZONTAL) gcode = `M960 S2 P${val}`;
    if (type == LEDS.LED_NOZZLE) gcode = `M960 S4 P${val}`;
    if (type == LEDS.LED_TOOLHEAD) gcode = `M960 S5 P${val}`;
    if (type == LEDS.ALL_LEDS) gcode = `M960 S0 P${val}`;
    return `${gcode}\n`;
}

function M973({action, num = 1, expose = 0}) { /* nozzle camera stream */
    switch (action) {
        case OV2740.OFF:
            return "M973 S4\n";
        case OV2740.ON:
            return "M973 S3 P1\n";
        case OV2740.AUTOEXPOSE:
            return "M973 S1\n";
        case OV2740.EXPOSE:
            return `M973 S${num} P${expose}\n`; // Example: M973 S2 P600
        case OV2740.CAPTURE:
            return `M971 S${num} P${expose}\n`;
        default:
            return "M973 S4\n";
    }
}
function M201(z){
    return `M201 Z${z}\n`;
}
function  M622(j){
    return `M622 J${j}\n`;
}
function  M623(){
    return 'M623\n';
}
function  M83(){
    return 'M83\n';
}


