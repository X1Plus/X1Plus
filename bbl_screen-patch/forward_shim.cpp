#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <sys/time.h>
#include <unistd.h>
#include <stdarg.h>
#include <pthread.h>
#include <sys/mman.h>

#include <iostream>
#include <regex>
#include <vector>
#include <string>

#include "vendor/nlohmann/json.hpp"

#define PRINTF_BLUE(s, ...) do { printf("\x1B[1;96m" s "\x1B[0m", ##__VA_ARGS__); fflush(stdout); } while(0)

/* To enable AMS2/AMSHT support, we need to teach an old forward to talk to
 * a new MC (getting a new forward to run on an old AP FW version might also
 * have worked, but this seemed easier up until it was too late to give up).
 *
 * The general game plan for getting an old forward to talk to a new MC is:
 *
 *   - The AMS protocol has changed to "AMSv2" in the new MC, generally
 *     referring to AMSes as two bytes (AMS ID + slot ID) rather than a
 *     single byte with the LSBs representing the slot.  An old forward
 *     still only can speak of up to four AMSes, 0 through 3, so we
 *     internally remap AMS IDs that we detect from an "advanced" MC into
 *     the old forward's namespace.
 *
 *   - Once we have remapping primitives available, we can now patch forward
 *     to use them.  We implement all of the inbound AMSv2 commands and
 *     responses, and map them as appropriate to the original forward's
 *     understanding of AMSv1 commands and responses using our AMS ID
 *     mapping (and if we have to store other data, we do that too).
 *
 *   - Also, AMS HTs have an ID of 0x80, 0x81, ..., and have a different
 *     mcproto destination ID.  `upgrade` doesn't know how to talk to these,
 *     so we help it out by patching its outbound requests using our mapping
 *     table, and by patching AMS HT requests to have the right destination. 
 *     Then, we patch the responses as appropriate, as well.
 *
 *   - There are a handful of Gcode commands from the slicer or from
 *     bbl_screen that use an "old" syntax for how to talk to the AMS
 *     (asking for "gcode-logical" toolheads, rather than physical
 *     toolheads).  We intercept and remap those.
 *
 *   - We need to communicate new data outbound; any time forward doesn't
 *     know how to collect data, we patch the data transmit routines with
 *     data that we stash in sidecar variables.
 *
 *   - And, we want to implement the new drying functionality!  So we
 *     intercept inbound requests, and patch those to generate MC commands,
 *     if necessary.
 */

/* TODO:
 *  validate implementation of mc_ams_flush_param_cb
 *  maybe figure out what is the other parameter in mc_ams_flush_param_cb? 
 *  support command: "auto_stop_ams_dry" -- may not actually be triggered
 */

using namespace nlohmann;

#ifdef __cplusplus
#define EXTERN_C extern "C"
#else
#define EXTERN_C
#endif

/*** forward / mcproto constants ***/

enum dm_id {
    DM_MC     = 0x0300,
    DM_AP     = 0x0600,
    DM_AMS    = 0x0700,
    DM_AHB    = 0x0e00,
    DM_EXT    = 0x0f00,
    DM_AMS_HT = 0x1800,
};

enum msg_type {
    /* class 0x01 */
    MSG_GET_VERSION         = 0x03,
    
    /* class 0x02 */
    MSG_DDS_RECORDER                = 0x08,
    MSG_AMS_REPORT                  = 0x0f,
    MSG_AMS_TRAY_INFO_READ          = 0x11,
    MSG_GCODE_LINE_HANDLE           = 0x16,
    MSG_AMS_MAPPING                 = 0x17,
    MSG_AMS_TRAY_INFO_WRITE         = 0x18,
    MSG_AMS_TRAY_CONSUMPTION        = 0x1c,
    MSG_PACK_GET_PART_INFO          = 0x1d,
    MSG_AMS_V2_AMS_INFO_UPDATE      = 0x1f,
    MSG_AMS_V2_AMS_MAPPING          = 0x20,
    MSG_AMS_V2_AMS_TRAY_CONSUMPTION = 0x23,
    MSG_AMS_V2_AMS_FILAMENT_DRYING  = 0x2c,
    MSG_AMS_V2_AMS_FLUSH_PARAM      = 0x3b,
    
    /* class 0x04 */
    MSG_GET_MODULE_SN       = 0x02,
};

struct CProtocal;
struct CGparser;
struct packet_message_t;

#if defined(FIRMWARE_00_00_32_39)
#  include "forward_defs.00.00.32.39.h"
#else
#  error no offsets defined for this firmware?
#endif

// We don't want to patch if we're still running an old MC -- that would
// break the old MC's AMS support. 
//
// The below is set to true if we receive any indication that the attached
// MC speaks the new protocol, set to false if we receive indication that
// the MC is speaking the old protocol to us.
//
// any time we would do a new->old translation, check this!
bool mc_speaks_new_protocol = false;

void mc_spoke_new_protocol() {
    if (!mc_speaks_new_protocol) {
        PRINTF_BLUE("forward_shim: switching to new-style MC protocol\n");
    }
    mc_speaks_new_protocol = true;
}

void mc_spoke_old_protocol() {
    if (mc_speaks_new_protocol) {
        PRINTF_BLUE("forward_shim: switching to old-style MC protocol\n");
    }
    mc_speaks_new_protocol = false;
}

int CProtocal_send_mcu_packet_override(CProtocal *_this, void *payload, size_t payload_length, uint32_t req, uint32_t dest, uint32_t src, uint32_t msg_id, uint32_t msg_class, uint32_t param_8);

/*** AMS mapping ***/

/* On new MCs, you can have up to 4 AMS-legacy and up to 16 AMS-HT (and the
 * AMS HT are all mapped in a different namespace than AMS/AMS2 -- they have
 * the high bit set, 0x80).  But this `forward` only understands four AMSes
 * at all.  So, we have to map AMS-HTs into the AMS namespace.
 *
 * From here on out, we refer to AMS IDs on the AP-to-MC interface as
 * "physical" IDs, and we refer to AMS IDs inside of `forward` and beyond as
 * "logical" IDs.
 */

enum hw_type_e {
    UNKNOWN,
    AMS,
    N3F,
    N3S,
};

struct tray_info {
    char tray_type[32];
};

struct ams_info {
    uint8_t phys_id;
    int temp_dC;
    int humidity;
    int humidity_index;
    int dry_sta;
    int adapter_sta; /* 02 if plugged in on AMS HT, 0 if unplugged on AMS HT or on AMS 1, 04 if plugged in on AMS 2 Pro, 01 if unplugged on AMS 2 Pro */
#define AMS_INFO_ADAPTER_STA_AMS_HT_PLUGGED_IN    0x02
#define AMS_INFO_ADAPTER_STA_AMS_2_PRO_PLUGGED_IN 0x04
    
    /* insane, the AMS doesn't tell us when it'll be done -- we just have to
     * keep track of since we set it.  if forward restarts, we lose it!  */
    time_t dry_completion_time;
    
    hw_type_e hw_type; // grabbed from get_version response
    
    tray_info trays[4];
};
struct ams_info ams_info[4] = {}; /* indexed by logical AMS */

uint8_t ams_phys_to_log(uint8_t phys_id) {
    if (!mc_speaks_new_protocol) {
        return phys_id;
    }
    for (int i = 0; i < 4; i++) {
        if (ams_info[i].phys_id == phys_id)
            return i;
    }
    return 0xFF;
}

/*** JSON-side overrides ***/

static pthread_mutex_t _dry_response_wait_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t _dry_response_wait_cvar = PTHREAD_COND_INITIALIZER;
static bool _dry_response_did_respond = 0;
static uint8_t _dry_response_ams_id = 0;
static uint32_t _dry_response_code = 0;

extern "C" void update_ams_object_with_flags_override_C(void *ams_obj, json &j, int param3) {
    j["supports_ams_v2"] = mc_speaks_new_protocol;
    if (!mc_speaks_new_protocol)
        return;

    j["tray_exist_bits_raw"] = j["tray_exist_bits"];
    j["tray_is_bbl_bits_raw"] = j["tray_is_bbl_bits"];
    j["tray_read_done_bits_raw"] = j["tray_read_done_bits"];
    j["tray_reading_bits_raw"] = j["tray_reading_bits"];

    // We need to remap tray_cur, tray_tar, etc. from MC physical, into
    // forward logical, and then back into "logical AMS-HT" device
    // space.  Ugh!
#    define FIX_TRAY(x) do { \
        int i = stoi(j["tray_"#x].template get<std::string>()); \
        if (i >= 128 && i < 160) { \
            i = 0x80 | ams_phys_to_log(i); \
        } \
        j["tray_"#x] = std::to_string(i); \
    } while(0)
    FIX_TRAY(now);
    FIX_TRAY(pre);
    FIX_TRAY(tar);
    
    for (auto &ams: j["ams"]) {
        auto id_s = ams["id"].template get<std::string>();
        int id = atoi(id_s.c_str());
        //PRINTF_BLUE("JSON CREATED FOR AMS ID %d\n", id);
        
        /* dry_time: number, minutes remaining in dry operation */
        struct timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        if (ams_info[id].dry_sta == 0) {
            ams["dry_time"] = 0;
        } else if (ts.tv_sec < ams_info[id].dry_completion_time) {
            ams["dry_time"] = (ams_info[id].dry_completion_time - ts.tv_sec) / 60;
        } else {
            /* we are drying but we do not know how much longer is left */
            ams["dry_time"] = 1;
        }
        
        ams["temp"] = std::to_string(float(ams_info[id].temp_dC) / 10.0);
        ams["humidity_raw"] = std::to_string(ams_info[id].humidity);
        ams["humidity"] = std::to_string(ams_info[id].humidity_index);
        ams["adapter_status"] = ams_info[id].adapter_sta;
        
        if (ams_info[id].hw_type == N3S) {
            /* scrub the rest of those trays */
            auto trays = ams["tray"].template get<json::array_t>();
            trays.resize(1);
            ams["tray"] = trays;
            ams["info"] = "2004"; /* N3S */
            ams["id"] = std::to_string(id + 128);
            
            /* ugh */
            char xbuf[8];
            int was_present;
            
            int ams_exist_bits = stoi(j["ams_exist_bits"].template get<std::string>(), nullptr, 16);
            ams_exist_bits &= ~(1 << id);
            ams_exist_bits |= (1 << (id + 4));
            snprintf(xbuf, sizeof(xbuf), "%x", ams_exist_bits);
            j["ams_exist_bits"] = std::string(xbuf);
            
            // Keep ams_exist_bits_raw for upgrade -- otherwise if forward
            // restarts after upgrade, upgrade gets confused
            //j["ams_exist_bits_raw"] = std::string(xbuf);

#define SMASH_TRAY_GUY(what) \
            int what##_bits = stoi(j[#what "_bits"].template get<std::string>(), nullptr, 16); \
            was_present = (what##_bits >> (id * 4)) & 1; \
            what##_bits &= ~(1 << (id * 4)); \
            what##_bits |= (was_present << (id + 16)); \
            snprintf(xbuf, sizeof(xbuf), "%x", what##_bits); \
            j[#what "_bits"] = std::string(xbuf);
            
            SMASH_TRAY_GUY(tray_exist)
            SMASH_TRAY_GUY(tray_is_bbl)
            SMASH_TRAY_GUY(tray_read_done)
            SMASH_TRAY_GUY(tray_reading)
        } else if (ams_info[id].hw_type == N3F) {
            ams["info"] = "03";
        } else {
            ams["info"] = "01"; /* AMS */
        }
    }
}

extern "C" int handle_print_dds_message_override(CGparser *_this, json &j, int param3) {
    std::cout << j << std::endl;
    try {
        if (j["command"] == "ams_filament_drying") {
            // mqtt_pub '{"print":{"command":"ams_filament_drying","ams_id":128,"mode":1,"temp":75,"duration":60,"humidity":0,"rotate_tray":false,"sequence_id":"1234"}}'
            struct __attribute__((packed)) ams_dry_request {
                uint8_t ams_id;
                uint8_t enable;
                uint8_t temp;
                uint32_t time_minutes;
                uint8_t rotate_enable;
                uint8_t cooling_temp;
                uint8_t r_l_p;
            } req;
            
            int ams_id = j["ams_id"];
            int mode = j["mode"]; /* 0 is off, 1 is on */
            int cooling_temp = 55; // optional
            try {
                cooling_temp = j["cooling_temp"]; /* also known as "c_d_t" */
                if (cooling_temp < 40) {
                    cooling_temp = 55;
                }
            } catch(...) { };
            int temp = j["temp"];
            int duration = j["duration"];
            // int humidity = j["humidity"];
            bool rotate_tray = j["rotate_tray"];
            
            json rv = json {
                { "command", "ams_filament_drying" },
                { "ams_id", ams_id },
                { "mode", mode },
                { "cooling_temp", cooling_temp },
                { "temp", temp },
                { "duration", duration },
                { "rotate_tray", rotate_tray },
                { "sequence_id", j["sequence_id"] },
            };
            
            if (!mc_spoke_new_protocol) {
                rv["reason"] = "mc_not_new_enough";
                rv["result"] = "fail";
                goto publish_result;
            }

            ams_id &= 0x7F;
            
            if (ams_id >= 4) {
                rv["reason"] = "bad_ams_id";
                rv["result"] = "fail";
                goto publish_result;
            }
            
            // check adapter status
            if (ams_info[ams_id].adapter_sta != AMS_INFO_ADAPTER_STA_AMS_HT_PLUGGED_IN &&
                ams_info[ams_id].adapter_sta != AMS_INFO_ADAPTER_STA_AMS_2_PRO_PLUGGED_IN) {
                rv["reason"] = "ams_not_plugged_in";
                rv["result"] = "fail";
                goto publish_result;
            }
            
            pthread_mutex_lock(&_dry_response_wait_mutex);
            _dry_response_did_respond = 0;
            pthread_mutex_unlock(&_dry_response_wait_mutex);
            
            // send the packet
            req.ams_id = ams_info[ams_id].phys_id;
            req.enable = mode;
            req.temp = temp;
            req.cooling_temp = cooling_temp;
            req.time_minutes = duration * 60;
            req.rotate_enable = rotate_tray;
            req.r_l_p = 0;
            CProtocal_send_mcu_packet_override(_this->protocal, &req, sizeof(req), true, 0x300, 0x600, 0x2c, 2, true);
            
            
            /* in the original forward, they block here for one second, so
             * we can too.
             */
            struct timeval now;
            struct timespec timeout;
            gettimeofday(&now, NULL);
            timeout.tv_sec = now.tv_sec + 1;
            timeout.tv_nsec = now.tv_usec * 1000;

            pthread_mutex_lock(&_dry_response_wait_mutex);
            while (!_dry_response_did_respond && (pthread_cond_timedwait(&_dry_response_wait_cvar, &_dry_response_wait_mutex, &timeout) != ETIMEDOUT))
                ;
            
            if (!_dry_response_did_respond) {
                rv["result"] = "timeout";
                pthread_mutex_unlock(&_dry_response_wait_mutex);
                goto publish_result;
            }
            
            if (_dry_response_ams_id != req.ams_id) {
                rv["result"] = "fail";
                rv["reason"] = "wrong AMS ID returned? WTF";
                pthread_mutex_unlock(&_dry_response_wait_mutex);
                goto publish_result;
            }
            
            if (_dry_response_code != 0) {
                rv["result"] = "fail";
                rv["err_code"] = _dry_response_code;
                pthread_mutex_unlock(&_dry_response_wait_mutex);
                goto publish_result;
            }
            
            pthread_mutex_unlock(&_dry_response_wait_mutex);

            rv["result"] = "success";

            if (req.enable) {
                struct timespec ts;
                clock_gettime(CLOCK_MONOTONIC, &ts);
                ams_info[ams_id].dry_completion_time = ts.tv_sec + req.time_minutes * 60;
            } else {
                ams_info[ams_id].dry_completion_time = 0;
            }
            
publish_result:
            CGparser_publish_json(_this, rv, 0);
            return 0;
        } else if (j["command"] == "gcode_line") {
            if (!mc_speaks_new_protocol) {
                return handle_print_dds_message_orig(_this, j, param3);
            }

            /* for AMS HT: AMS ID 128 is needed fo rslicer, but it sends P512 rather
             * than P16?  P16 is an OK option, but P512 triggers (ams << 8
             * | slot) mode -- needs to be P32768.  looks like the root
             * cause is that orca/bbs, when in "new-style forward" mode,
             * switches to a different command type that does not have this
             *  bug...  maybe we can just intercept the gcode request
             * command and fix it up? 
             */
            std::string param = j["param"].template get<std::string>();
            const std::regex regex_m620("M620 ([A-Z])(\\d+) \n");
            std::smatch pieces;
            if (std::regex_match(param, pieces, regex_m620)) {
                std::string letter = pieces[1].str();
                int tray = atoi(pieces[2].str().c_str());
                if (tray >= 512) {
                    /* this must have been the slicer trying to send ams_id 0x80 + 0 */
                    int newtray = tray - 512;
                    PRINTF_BLUE("forward: fixing up M620 %s%d -> %d for slicer\n", letter.c_str(), tray, newtray);
                    tray = newtray;
                }
                
                if ((tray >> 2) < 4) {
                    /* this must have been the bbl_screen trying to poke the AMS HT */
                    int new_phys = ams_info[tray >> 2].phys_id;
                    int newtray = (new_phys << 8) + (tray & 0x3);
                    PRINTF_BLUE("forward: fixing up M620 %s%d -> %d for screen\n", letter.c_str(), tray, newtray);
                    char s[32];
                    snprintf(s, sizeof(s), "M620 %s%d \n", letter.c_str(), newtray);
                    j["param"] = s;
                }
            }
        } else if (j["command"] == "ams_change_filament") {
            if (!mc_speaks_new_protocol) {
                return handle_print_dds_message_orig(_this, j, param3);
            }

            /* for AMS HT: ams_change_filament command "target" goes wrong
             * an dshould be rewritten to take "slot_id"
             * https://github.com/OrcaSlicer/OrcaSlicer/blob/504a5d3b704fba8c0fac410cf9702f7bcf611f95/src/slic3r/GUI/DeviceManager.cpp#L1528
             * */
            try {
                int ams_id = j["ams_id"];
                int slot_id = j["slot_id"];
                int target = j["target"];
                ams_id &= 0x7F;
                if (ams_id < 4) {
                    ams_id = ams_info[ams_id].phys_id;
                }
                if (slot_id == 254) { /* "load from external spool" */
                    j["target"] = target = 254;
                } else if (slot_id == 255) { /* "unload" */
                    j["target"] = target = 255;
                } else {
                    j["target"] = target = (ams_id << 8) + slot_id;
                }
                PRINTF_BLUE("forward: rewriting new-style ams_change_filament ams_id %d slot_id %d -> target %d\n", ams_id, slot_id, target);
            } catch(...) { try {
                int target = j["target"];
                int old_target = target;
                if (target == 254) { /* "load from external spool" */
                    j["target"] = target = 254;
                } else if (target != 255) { /* "unload" */
                    int ams_id = target >> 2;
                    int slot_id = target & 3;
                    if (ams_id < 4) {
                        ams_id = ams_info[ams_id].phys_id;
                    }
                    j["target"] = target = (ams_id << 8) + slot_id;
                }
                PRINTF_BLUE("forward: rewriting old-style ams_change_filament target %d -> target %d\n", old_target, target);
            } catch(...) {
                PRINTF_BLUE("forward: ams_change_filament was neither new-style nor old-style?\n");
            } }
        }
        
        /* maybe there's an ams_mapping to convert? */
#if 0
        /* The ams_mapping2 is sometimes just completely wrong!  I guess it
         * need to be merged with ams_mapping?  The old one should always be
         * safe, anyway.  */
        try {
            std::vector<int> new_ams_mapping;
            for (auto map: j["ams_mapping2"]) {
                int ams_id = map["ams_id"];
                int slot_id = map["slot_id"];
                new_ams_mapping.push_back((ams_id << 8) + slot_id);
            }
            j["ams_mapping"] = new_ams_mapping;
            PRINTF_BLUE("forward: converted new ams_mapping\n");
            std::cout << j["ams_mapping"] << std::endl;
        } catch (...) { }
#endif

        /* Normalize AMS mappings to forward-internal format -- AMS ID in
         * 0-3, slot ID in 0-3.  We'll re-normalize later to the new MC
         * format in the cb_amsv2_mapping output rewrite (mapping 2,0x17 ->
         * 2,0x20).  That way, forward can use its little-brain knowledge of
         * what filament is in what slot to remap.
         */
        try {
            std::vector<int> new_ams_mapping;
            for (int map: j.at("ams_mapping")) {
                PRINTF_BLUE("forward: input ams_mapping: %d\n", map);
                if (map == -1) {
                    new_ams_mapping.push_back(-1);
                } else {
                    int ams_id = map >> 2;
                    int slot_id = map & 3;
                    
                    if (ams_id & 0x80) {
                        ams_id &= 0x7F;
                    }
                    new_ams_mapping.push_back((ams_id << 2) + slot_id);
                }
            }
            if (mc_speaks_new_protocol) {
                j["ams_mapping"] = new_ams_mapping;
                PRINTF_BLUE("forward: converted old ams_mapping\n");
                std::cout << j["ams_mapping"] << std::endl;
            }
        } catch (...) { }

    } catch(...) {
        PRINTF_BLUE("forward: hmmmmm, JSON exception of some kind.  hope it wasn't important\n");
    }
    return handle_print_dds_message_orig(_this, j, param3);
}

extern "C" void *replace_next_extruder_filament_temp_override(std::string &path, void *b, std::string &next_extruder, std::string &new_temp) {
    PRINTF_BLUE("forward: replace_next_extruder_filament_temp_override(%s, %p, %s, %s)\n", path.c_str(), b, next_extruder.c_str(), new_temp.c_str());
    if (next_extruder == "254" && mc_speaks_new_protocol) {
        /* see, i.e.,
         * https://github.com/OrcaSlicer/OrcaSlicer/blob/e81e7b9a23f9f429a0134b0e3c35ffbb107f027a/src/slic3r/GUI/DeviceManager.cpp#L1536-L1538
         * -- new MC needs "AMS ID 254, slot ID 0" as the slot ID it chooses for spool */
        PRINTF_BLUE("forward: overriding next_extruder for external spool!\n");
        next_extruder = "65280"; // AMS ID 255, slot id 0.  note: this works only as long as the current spool is not already loaded!
    }
    return replace_next_extruder_filament_temp_orig(path, b, next_extruder, new_temp);
}

/*** AMS temperature table and mcproto implementation for lookups ***/

struct ams_temp_table {
    const char *name;
    uint32_t a; /* no idea what these are */
    uint32_t b;
    uint32_t c;
    uint32_t cool_temp;
};

struct ams_temp_table ams_temp_table[] = {
    { "PLA", 0x37, 8, 0x28, 0x37 },
    { "PETG", 0x41, 0xc, 0x3c, 0x41 },
    { "PET", 0x50, 0xc, 0x2d, 0x50 },
    { "TPU", 0x4b, 0x12, 0x28, 0x28 },
    { "ABS", 0x50, 8, 0x46, 0x46 },
    { "ASA", 0x50, 8, 0x46, 0x50 },
    { "PC", 0x50, 8, 0x46, 0x5a },
    { "PA", 0x55, 0xc, 0x46, 0x50 },
    { "PVA", 0x50, 0xc, 0x3c, 0x2d },
    { "PAHT", 0x55, 0xc, 0x46, 100 },
    { "Support For PA/PET", 0x50, 0xc, 0x46, 0x50 },
    { "Support For ABS", 0x50, 4, 0x46, 0x46 },
    { "Support For PLA/PETG", 0x3c, 0xc, 0x28, 0x28 },
    { "PPA", 100, 0xc, 0x46, 0x96 },
    { "PPS", 0x6e, 0xc, 0x46, 0x96 },
};

int CProtocal_handle_mc_ams_flush_param(CProtocal *_this) {
    struct __attribute__((packed)) {
        uint8_t type;
        uint8_t const_2;
        uint16_t rv;
    } rv;

    mc_spoke_new_protocol();
    
    uint8_t ams_id = ams_phys_to_log(_this->packet->payload[0]);
    uint8_t tray_id = _this->packet->payload[1];
    if (ams_id > 3)
        ams_id = 0;
    if (tray_id > 3)
        tray_id = 0;
    
    rv.type = _this->packet->payload[2];
    rv.const_2 = 2;
    
    PRINTF_BLUE("CProtocal_handle_mc_ams_flush_param: %02x %02x %02x %02x\n",
        _this->packet->payload[0], _this->packet->payload[1], _this->packet->payload[2], _this->packet->payload[3]);
    
    switch (rv.type) {
    case 0: {
        PRINTF_BLUE("CProtocal_handle_mc_ams_flush_param: asked for type get_ams_flush_param, no idea how to handle this\n");
        rv.rv = 0xFFFF;
        break;
    }
    case 1: {
        int found = 0;
        for (int i = 0; i < sizeof(ams_temp_table)/sizeof(ams_temp_table[0]); i++) {
            if (!strcmp(ams_temp_table[i].name, ams_info[ams_id].trays[tray_id].tray_type)) {
                PRINTF_BLUE("CProtocal_handle_mc_ams_flush_param: asked for cooltemp for tray %d %d, giving answer for %s\n", ams_id, tray_id, ams_temp_table[i].name);
                rv.rv = ams_temp_table[i].cool_temp;
                found = 1;
                break;
            }
        }
        if (!found) {
            PRINTF_BLUE("CProtocal_handle_mc_ams_flush_param: asked for cooltemp for tray %d %d not in table, giving conservative answer\n", ams_id, tray_id);
            rv.rv = 0x37;
        }
        break;
    }
    default: {
        PRINTF_BLUE("CProtocal_handle_mc_ams_flush_param: unknown flush_param\n");
        return 0;
    }
    }
    
    CProtocal_send_mcu_packet_override(_this, &rv, sizeof(rv), false, 0x300, 0x600, 0x3b, 0x2, false);
    
    return 0;
}

/*** AP-to-MC overrides ***/

bool ams_is_enabled = true;

int CProtocal_send_mcu_packet_override(CProtocal *_this, void *payload, size_t payload_length, uint32_t req, uint32_t dest, uint32_t src, uint32_t msg_id, uint32_t msg_class, uint32_t param_8) {
    if (!mc_speaks_new_protocol) {
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dest, src, msg_id, msg_class, param_8);
    }

    //PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: %04x -> %04x, cls %02x, id %02x, pl len %d\n", src, dest, msg_class, msg_id, payload_length);
    if (((msg_class == 0x01 && msg_id == MSG_GET_VERSION) ||
         (msg_class == 0x04 && msg_id == MSG_GET_MODULE_SN)) &&
        (dest == DM_EXT || dest == DM_AHB)) {
        // When upgrade spams this, it can jam up the MC's output queue to
        // AMS.  Rate limit it to one every 5 seconds.
        static struct timespec last_req[4];
        struct timespec now, dt;
        clock_gettime(CLOCK_MONOTONIC, &now);
        
        int req_id = 0;
        if (msg_id == MSG_GET_MODULE_SN) req_id |= 1;
        if (dest == DM_AHB) req_id |= 2;
        
        dt.tv_sec  = now.tv_sec - last_req[req_id].tv_sec;
        dt.tv_nsec = now.tv_nsec - last_req[req_id].tv_nsec;
        if (dt.tv_nsec < 0) {
            dt.tv_sec--;
            dt.tv_nsec += 1000000000;
        }
        
        if (dt.tv_sec < 2) {
            //PRINTF_BLUE("CProtocal_send_mcu_packet_override: nerfing req %x for dm %x\n", msg_id, dest);
            return 1;
        }
        //PRINTF_BLUE("CProtocal_send_mcu_packet_override: allowing req %x for dm %x through\n", msg_id, dest);
        last_req[req_id] = now;
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dest, src, msg_id, msg_class, param_8);
    } else if (msg_class == 0x02 && msg_id == MSG_GCODE_LINE_HANDLE) {
        char *m620_e = (payload_length >= 4) ? (char *)memmem((char *)payload + 4, payload_length - 4, "M620 E", 6) : NULL;
        // new MC always requires the AMS to be on; AMS-off is handled by
        // pretending that AMS is on and sending an 0xFF00 AMS routing
        if (m620_e) {
            if (m620_e[6] == '0') {
                PRINTF_BLUE("CProtocal_send_mcu_packet_override: found M620 E0, patching to M620 E1; use_ams = %d\n", _this->gparser.use_ams);
                m620_e[6] = '1';
            } else {
                PRINTF_BLUE("CProtocal_send_mcu_packet_override: found M620 E1, use_ams = %d\n", _this->gparser.use_ams);
            }
        }
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dest, src, msg_id, msg_class, param_8);
    } else if (msg_class == 0x02 && msg_id == MSG_AMS_TRAY_CONSUMPTION) {
        /* this actually needed to be a link_ams_tray_consumption_v2 */
        uint8_t pl = *(uint8_t *)payload;
        uint8_t pl_new[4] =
            { (uint8_t)(pl >> 2), (uint8_t)(pl & 3), 0xAB, 0xCD }; /* last two bytes seem to be incrementing?  maybe just uninitialized memory on stack */
        //PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: rewriting link_ams_tray_consumption into link_ams_tray_consumption_v2\n");
        return CProtocal_send_mcu_packet_override(_this, pl_new, 4, req, dest, src, MSG_AMS_V2_AMS_TRAY_CONSUMPTION, 0x02, param_8);
    } else if (msg_class == 0x01 && msg_id == MSG_GET_VERSION && dest == DM_AMS) { /* AMS, get_version */
        uint8_t *pl = (uint8_t *)payload;
        if (pl[0] < 4) {
            pl[0] = ams_info[pl[0]].phys_id;
        }
        if (pl[0] & 0x80) {
            dest = DM_AMS_HT; /* all N3S (AMS HT) have destination 0x1800 */
        }
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dest, src, msg_id, msg_class, param_8);
    } else if (msg_class == 0x04 && msg_id == MSG_GET_MODULE_SN && dest == DM_AMS) { /* AMS, get_module_sn */
        uint8_t *pl = (uint8_t *)payload;
        if (pl[33] < 4) {
            pl[33] = ams_info[pl[33]].phys_id;
        }
        if (pl[33] & 0x80) {
            dest = DM_AMS_HT; /* all N3S (AMS HT) have destination 0x1800 */
        }
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dest, src, msg_id, msg_class, param_8);
    } else if (msg_class == 0x02 && msg_id == MSG_AMS_TRAY_INFO_READ && dest == DM_AMS) { /* AMS, tray_info */
        uint8_t *pl = (uint8_t *)payload;
        PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: tray info request for ams %d, tray %d\n", pl[0], pl[1]);
        if (pl[0] < 4) {
            pl[0] = ams_info[pl[0]].phys_id;
        }
        if (pl[0] & 0x80) {
            dest = DM_AMS_HT; /* all N3S (AMS HT) have destination 0x1800 */
        }
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dest, src, msg_id, msg_class, param_8);
    } else if (msg_class == 0x02 && msg_id == MSG_AMS_MAPPING) {
        /* ams_mapping needs to be rewritten to ams_v2_ams_mapping */
        struct __attribute__((packed)) ams_mapping {
            uint8_t len;
            uint8_t vers;
            uint16_t dest[0x20];
        };
        struct ams_mapping *old_map = (struct ams_mapping *)payload;
        struct ams_mapping new_map;
        memset(&new_map, 0xFF, sizeof(new_map));
        
        new_map.len = 0x20;
        new_map.vers = old_map->vers;
        PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: ams_mapping vers %02x\n", new_map.vers);
        if (!ams_is_enabled) {
            PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: ams_mapping: use_ams = false!\n");
        }
        for (int i = 0; i < 16; i++) {
            
            PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: ams_mapping %d = %02x\n", i, old_map->dest[i]);
            
            int ams_id_out = old_map->dest[i] >> 2;
            int slot_id_out = old_map->dest[i] & 3;
            
            /* recompute the destination AMS ID */
            if (old_map->dest[i] == 0xFE) {
                ams_id_out = 0xFF;
                slot_id_out = 0x00;
            } else if (ams_id_out < 4) {
                ams_id_out = ams_info[ams_id_out].phys_id;
                if (ams_id_out & 0x80) {
                    slot_id_out = 0;
                }
            } else {
                ams_id_out = 0xFF;
                slot_id_out = 0xFF;
            }
            uint16_t dest_id = (ams_id_out << 8) | slot_id_out;
            
            if (!ams_is_enabled) {
                // New MC does not support M620 E0, and if you want to not
                // use the AMS, you have to reply with an AMS mapping of
                // 0xFF00 (use external spool tray).
                dest_id = 0xff00;
            }
            
            PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: AMS slot %d -> %04x\n", i, dest_id);
            new_map.dest[i] = dest_id;
        }
        
        return CProtocal_send_mcu_packet_orig(_this, &new_map, sizeof(new_map), req, dest, src, MSG_AMS_V2_AMS_MAPPING, 0x2, param_8);
    } else if (msg_class == 0x02 && msg_id == MSG_AMS_TRAY_INFO_WRITE) {
        /* ams_tray_info_write needs to be updated to a new output AMS ID, and the correct DM ID */
        struct __attribute__((packed)) ams_tray_info_write {
            uint8_t ams_id;
            uint8_t tray_id;
            uint8_t fila_id[8];
            uint8_t color_rgba[4];
            uint16_t nozzle_temp_min;
            uint16_t nozzle_temp_max;
            uint8_t fila_type[16];
        };
        ams_tray_info_write *pl_cmd = (ams_tray_info_write *)payload;
        uint32_t dm_id = DM_MC;
        if (pl_cmd->ams_id < 4 && pl_cmd->tray_id < 4) {
            pl_cmd->ams_id = ams_info[pl_cmd->ams_id].phys_id;
            if (pl_cmd->ams_id & 0x80) {
                PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: overriding ams_tray_info_write for AMS HT\n");
                dm_id = DM_AMS_HT;
            } else {
                PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: overriding ams_tray_info_write for AMS classic\n");
                dm_id = DM_AMS;
            }
        } else {
            PRINTF_BLUE("forward: CProtocal_send_mcu_packet_override: not overriding ams_tray_info_write for ams_id %d, tray_id %d\n", pl_cmd->ams_id, pl_cmd->tray_id);
        }
        
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dm_id, src, msg_id, msg_class, param_8);
    } else {
        return CProtocal_send_mcu_packet_orig(_this, payload, payload_length, req, dest, src, msg_id, msg_class, param_8);
    }
}

/*** MC-to-AP overrides ***/

int (*CProtocal_original_ams_report)(CProtocal *) = NULL;
int CProtocal_handle_ams_report(CProtocal *_this) {
    mc_spoke_old_protocol();
    return CProtocal_original_ams_report(_this);
}

struct __attribute__((packed)) link_ams_report { /* 2, 0xf */
    uint8_t ams_exist;
    uint32_t tray_exist;
    uint16_t tray_read_done;
    uint16_t tray_reading;
    uint16_t tray_is_bbl;
    uint16_t insert_poweron_remain;
};


static struct link_ams_report prev_synth_link_ams_report = {};
static uint32_t force_ams_reread = 0;

struct __attribute__((packed)) ams_desc {
    uint8_t pl_id;        // 0
    uint8_t pl_len;       // 1
    uint8_t ams_id;       // 2
    uint16_t temperature; // 3, 4: 0.1C
    uint8_t unknown_3;    // 5
    uint8_t unknown_4;    // 6
    uint8_t humidity;     // 7: percent
    uint8_t unknown_6;    // 8
    uint8_t humidity_index; // 9
    uint8_t dry_sta;        // 10
    uint8_t adapter_sta;    // 11: 02 if plugged in, 00 if not
};

/* This is the meat of our work here: when MC sends us an AMSv2 data update,
 * we should 1) use it to assign logical-vs-physical AMS IDs, and then 2)
 * synthesize an AMSv1 report packet back to the legacy forward.
 *
 * When we have extra data that we can't represent in an AMSv1 packet --
 * like temperature, drying time, precise humidity, etc.  -- we store it in
 * the logical-AMS structure, struct ams_info.
 */

int CProtocal_handle_ams_v2_ams_info_update(CProtocal *_this) {
    mc_spoke_new_protocol();
    
    /* run once to assign logical AMS IDs to AMS HTs */
    uint32_t phys_ams_bitmap = 0;
    int len = _this->packet->packet_length - 15;
    uint8_t *pl = _this->packet->payload;
    
    while (len) {
        if (len < 2) {
            PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: not enough bytes left %d for a payload?\n", len);
            return 0;
        }

        int subpl_len = pl[1] + 2;
        if (len < subpl_len) {
            PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: not enough bytes left (%d) for subpayload %d bytes?\n", len, subpl_len);
            return 0;
        }
        
        switch (pl[0]) {
        case 0: { /* AMS descriptor */
            ams_desc *desc = (ams_desc *)pl;
            
            if (desc->ams_id & 0x80) {
                int ams_id = desc->ams_id & 0x7F;
                if (ams_id > 15) {
                    PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: AMS-HT ID is too big\n");
                    return 0;
                }
                phys_ams_bitmap |= 1 << (ams_id + 4);
            } else {
                if (desc->ams_id > 3)  {
                    PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: AMS ID is too big\n");
                    return 0;
                }
                if (ams_info[desc->ams_id].phys_id != desc->ams_id) {
                    memset(ams_info + desc->ams_id, 0, sizeof(struct ams_info));
                }
                ams_info[desc->ams_id].phys_id = desc->ams_id;
                phys_ams_bitmap |= 1 << desc->ams_id;
            }
            break;
        }
        default:
            break;
        }

        len -= subpl_len;
        pl += subpl_len;
    }
    
    /* now assign physical AMS-HT to logical AMS */
    uint32_t log_ams_bitmap = phys_ams_bitmap & 0xF;
    for (int i = 0; i < 16; i++) {
        if (phys_ams_bitmap & (1 << (i + 4))) {
            int log_id = 0;
            for (log_id = 0; log_id < 4; log_id++) {
                if (!(log_ams_bitmap & (1 << log_id))) {
                    break;
                }
            }
            if (log_id == 4) {
                PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: no logical AMS available for AMS-HT %d!\n", i);
                break;
            }
            log_ams_bitmap |= 1 << log_id;
            if (ams_info[log_id].phys_id != (0x80 | i)) {
                memset(ams_info+log_id, 0, sizeof(struct ams_info));
            }
            ams_info[log_id].phys_id = 0x80 | i;
        }
    }

    /* XXX: where did AMS temperature and humidity come in in amsv1? */
    struct link_ams_report synth_link_ams_report = {};
    
    /* now actually go process AMS status */
    len = _this->packet->packet_length - 15;
    pl = _this->packet->payload;
    while (len) {
        if (len < 2) {
            PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: not enough bytes left %d for a payload?\n", len);
            return 0;
        }

        int subpl_len = pl[1] + 2;
        if (len < subpl_len) {
            PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: not enough bytes left (%d) for subpayload %d bytes?\n", len, subpl_len);
            return 0;
        }
        
        //PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: pl type %d, %d bytes\n", pl[0], subpl_len);
        switch (pl[0]) {
        case 0: { /* AMS descriptor */
            struct __attribute__((packed)) ams_desc {
                uint8_t pl_id;        // 0
                uint8_t pl_len;       // 1
                uint8_t ams_id;       // 2
                uint16_t temperature; // 3, 4: 0.1C
                uint8_t unknown_3;    // 5
                uint8_t unknown_4;    // 6
                uint8_t humidity;     // 7: percent
                uint8_t unknown_6;    // 8
                uint8_t humidity_index; // 9
                uint8_t dry_sta;        // 10
                uint8_t adapter_sta;    // 11: 02 if plugged in, 00 if not
            };
            ams_desc *desc = (ams_desc *)pl;
            
            //PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: AMS descriptor: ID %d, temperature %d, ?3 %02x, ?4 %02x, humidity %d, ?6 %02x, dry_sta %d, adapter_sta %d, ?9 %02x\n",
            //   desc->ams_id, desc->temperature, desc->unknown_3, desc->unknown_4, desc->humidity, desc->unknown_6, desc->dry_sta, desc->adapter_sta, desc->unknown_9);
            
            int log_ams_id = ams_phys_to_log(desc->ams_id);
            if (log_ams_id > 3) {
                PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: no logcal AMS for physical AMS %02x\n", desc->ams_id);
                break;
            }
            
            synth_link_ams_report.ams_exist |= (1 << log_ams_id);
            
            /* XXX: we will just slam temperature and humidity the long way into the AMS structure, I guess */
            ams_info[log_ams_id].temp_dC = desc->temperature;
            ams_info[log_ams_id].humidity = desc->humidity;
            ams_info[log_ams_id].humidity_index = desc->humidity_index;
            ams_info[log_ams_id].dry_sta = desc->dry_sta;
            ams_info[log_ams_id].adapter_sta = desc->adapter_sta;
            
            break;
        }
        case 1: { /* tray descriptor */
            struct __attribute__((packed)) tray_desc {
                uint8_t pl_id;
                uint8_t pl_len;
                uint8_t ams_id;
                uint8_t slot_id;
                uint8_t status;
            };
            tray_desc *desc = (tray_desc *)pl;

            // PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: tray descriptor: ams %d, slot %d, status %02x\n",
            //    desc->ams_id, desc->slot_id, desc->status);

            int log_ams_id = ams_phys_to_log(desc->ams_id);
            if (log_ams_id > 3) {
                break;
            }

            synth_link_ams_report.tray_exist |= 1 << (log_ams_id * 4 + desc->slot_id);
            if (desc->status & 1) {
                synth_link_ams_report.tray_read_done |= 1 << (log_ams_id * 4 + desc->slot_id);
            }
            if (desc->status & 2) {
                synth_link_ams_report.tray_reading |= 1 << (log_ams_id * 4 + desc->slot_id);
            }
            if (desc->status & 4) {
                synth_link_ams_report.tray_is_bbl |= 1 << (log_ams_id * 4 + desc->slot_id);
            }
            break;
        }
        case 2: { /* AMS flags */
            struct __attribute__((packed)) ams_flags {
                uint8_t pl_id;
                uint8_t pl_len;
                uint8_t insert_poweron_remain;
            };
            ams_flags *desc = (ams_flags *)pl;
            // PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: ams flags: insert_poweron_remain %02x\n", desc->insert_poweron_remain);
            synth_link_ams_report.insert_poweron_remain = desc->insert_poweron_remain;
            break;
        }
        case 3: { /* extruder information */
            //PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: unhandled: extruder information\n");
            break;
        }
        default:
            PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: unknown subpayload %d\n", pl[0]);
            return 0;
        }

        len -= subpl_len;
        pl += subpl_len;
    }
    
    uint8_t *orig_pl = _this->packet->payload;
    int orig_len = _this->packet->packet_length;
    
    if (memcmp(&prev_synth_link_ams_report, &synth_link_ams_report, sizeof(synth_link_ams_report)) || force_ams_reread) {
        PRINTF_BLUE("forward: CProtocal_handle_ams_v2_ams_info_update: synthesizing legacy packet\n");

        memcpy(&prev_synth_link_ams_report, &synth_link_ams_report, sizeof(synth_link_ams_report));
        
        /* new mc seems to always report tray_is_bbl?  so if we complete a
         * write, we just invalidate the tray.  XXX: this is a little goofy:
         * we skip this only once, and don't synthesize the transition back
         * to is_bbl!  and then when it transitions to is_bbl again later,
         * it will be wrong and trigger another read.  but at least we don't
         * trigger two back to back right away
         */
        synth_link_ams_report.tray_is_bbl &= ~force_ams_reread;
        _this->packet->payload = (uint8_t *)&synth_link_ams_report;
        _this->packet->packet_length = 15 + sizeof(synth_link_ams_report);
        CProtocal_original_ams_report(_this);
    
        _this->packet->payload = orig_pl;
        _this->packet->packet_length = orig_len;
    }

    force_ams_reread = 0;
    
    return 0;
}

/* The other overrides mostly just convert logical to physical AMS IDs, or
 * two-byte to one-byte formats.  */

int (*CProtocal_original_get_version)(CProtocal *) = NULL;
int CProtocal_handle_get_version(CProtocal *_this) {
    if (_this->packet->src_addr == DM_AMS_HT || _this->packet->src_addr == DM_AMS) {
        _this->packet->payload[20] = ams_phys_to_log(_this->packet->payload[20]);
        _this->packet->src_addr = DM_AMS;
    }
    if (_this->packet->src_addr == DM_AMS) {
        // this is an AMS, stash its hardware version
        int ams_id = _this->packet->payload[20];
        if (ams_id < 4) {
            if (!memcmp(_this->packet->payload + 4, "AMS", 3)) {
                ams_info[ams_id].hw_type = AMS;
            } else if (!memcmp(_this->packet->payload + 4, "N3F", 3)) {
                ams_info[ams_id].hw_type = N3F;
            } else if (!memcmp(_this->packet->payload + 4, "N3S", 3)) {
                ams_info[ams_id].hw_type = N3S;
            } else {
                ams_info[ams_id].hw_type = UNKNOWN;
            }
        }
    }
    return CProtocal_original_get_version(_this);
}

int (*CProtocal_original_get_module_sn)(CProtocal *) = NULL;
int CProtocal_handle_get_module_sn(CProtocal *_this) {
    if (_this->packet->src_addr == DM_AMS_HT || _this->packet->src_addr == DM_AMS) {
        _this->packet->payload[65] = ams_phys_to_log(_this->packet->payload[65]);
        _this->packet->src_addr = DM_AMS;
    }
    return CProtocal_original_get_module_sn(_this);
}

int (*CProtocal_original_ams_tray_info_read)(CProtocal *) = NULL;
int CProtocal_handle_ams_tray_info_read(CProtocal *_this) {
    if (_this->packet->payload[0] != 0xFF) {
        _this->packet->payload[0] = ams_phys_to_log(_this->packet->payload[0]);
    }
    
    /* store the tray type in our local cache */
    if (_this->packet->payload[0] < 4 && _this->packet->payload[1] < 4) {
        char *tray_type = ams_info[_this->packet->payload[0]].trays[_this->packet->payload[1]].tray_type;
        memcpy(tray_type, _this->packet->payload + 27, 16);
        tray_type[16] = 0;
    }
    
    return CProtocal_original_ams_tray_info_read(_this);
}

int (*CProtocal_original_ams_tray_info_write)(CProtocal *_this) = NULL;
int CProtocal_handle_ams_tray_info_write(CProtocal *_this) {
    uint8_t reread_req[3] = { _this->packet->payload[0], _this->packet->payload[1], 0x00 };

    if (_this->packet->payload[0] != 0xFF) {
        _this->packet->payload[0] = ams_phys_to_log(_this->packet->payload[0]);
    }

    PRINTF_BLUE("forward: CProtocal_handle_ams_tray_info_write: got ack for AMS %02x, tray %02x\n", _this->packet->payload[0], _this->packet->payload[1]);
    
    if (mc_speaks_new_protocol) {
        force_ams_reread |= 1 << (_this->packet->payload[0] * 4 + _this->packet->payload[1]);
        PRINTF_BLUE("forward: CProtocal_handle_ams_tray_info_write: set force_ams_reread to %08x and synthesize a reread\n", force_ams_reread);
    
        CProtocal_send_mcu_packet_override(_this, reread_req, 3, true, DM_AMS, DM_AP, MSG_AMS_TRAY_INFO_READ, 0x02, true);
    }
    
    return CProtocal_original_ams_tray_info_write(_this);
}

int CProtocal_handle_link_ams_tray_consumption_ack2(CProtocal *_this) {
    mc_spoke_new_protocol();

    PRINTF_BLUE("forward: rewriting link_ams_tray_consumption_ack2 to link_ams_tray_consumption_ack\n");
    _this->packet->payload[0] = (_this->packet->payload[0] << 2) | (_this->packet->payload[1]);
    memmove(_this->packet->payload + 1, _this->packet->payload + 2, _this->packet->packet_length - 0x10);
    
    return _this->packet_info[0x2][MSG_AMS_TRAY_CONSUMPTION].callback(_this);
}

int CProtocal_handle_ams_v2_ams_mapping(CProtocal *_this) {
    /* this is a request */
    mc_spoke_new_protocol();

    PRINTF_BLUE("forward: rewriting ams_v2_ams_mapping to ams_mapping\n");
    
    int orig_len = _this->packet->packet_length;
    _this->packet->packet_length = 15 + 0x22;
    
    int rv = _this->packet_info[0x2][MSG_AMS_MAPPING].callback(_this);
    
    _this->packet->packet_length = orig_len;
    return rv;
}

int CProtocal_handle_ams_filament_drying(CProtocal *_this) {
    mc_spoke_new_protocol();

    pthread_mutex_lock(&_dry_response_wait_mutex);
    _dry_response_did_respond = 1;
    _dry_response_ams_id = *(uint8_t *)(_this->packet->payload);
    _dry_response_code = *(uint32_t *)(_this->packet->payload + 1);
    
    PRINTF_BLUE("forward: AMS drying response, AMS ID %02x, resp %08x\n", _dry_response_ams_id, _dry_response_code);
    
    pthread_cond_broadcast(&_dry_response_wait_cvar);
    pthread_mutex_unlock(&_dry_response_wait_mutex);
    return 0;
}

int CProtocal_handle_ams_v2_packet(CProtocal *_this) {
    mc_spoke_new_protocol();

    PRINTF_BLUE("forward: packet cmdset %d, cmdid %d, len %d\n", _this->packet->cmd_set, _this->packet->cmd_id, _this->packet->packet_length);
    return 0;
}

int CProtocal_nop_recorder(CProtocal *_this) {
    // save some CPU and latency -- no need to publish all this noise, since
    // there is no recorder in X1Plus
    return 0;
}

extern "C" void CProtocal_setup_callbacks_override_C(CProtocal *_this) {
    _this->packet_info[0x2][MSG_DDS_RECORDER].callback = CProtocal_nop_recorder;
    CProtocal_original_get_version = _this->packet_info[0x1][MSG_GET_VERSION].callback;
    _this->packet_info[0x1][MSG_GET_VERSION].callback = CProtocal_handle_get_version;
    CProtocal_original_get_module_sn = _this->packet_info[0x4][MSG_GET_MODULE_SN].callback;
    _this->packet_info[0x4][MSG_GET_MODULE_SN].callback = CProtocal_handle_get_module_sn;
    CProtocal_original_ams_tray_info_read = _this->packet_info[0x2][MSG_AMS_TRAY_INFO_READ].callback;
    _this->packet_info[0x2][MSG_AMS_TRAY_INFO_READ].callback = CProtocal_handle_ams_tray_info_read;
    CProtocal_original_ams_tray_info_write = _this->packet_info[0x2][MSG_AMS_TRAY_INFO_WRITE].callback;
    _this->packet_info[0x2][MSG_AMS_TRAY_INFO_WRITE].callback = CProtocal_handle_ams_tray_info_write;
    CProtocal_original_ams_report = _this->packet_info[0x2][MSG_AMS_REPORT].callback;
    _this->packet_info[0x2][MSG_AMS_REPORT].callback = CProtocal_handle_ams_report;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_INFO_UPDATE].mcu_command_table_field = 2;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_INFO_UPDATE].callback = CProtocal_handle_ams_v2_ams_info_update;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_MAPPING].mcu_command_table_field = 2;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_MAPPING].callback = CProtocal_handle_ams_v2_ams_mapping;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_TRAY_CONSUMPTION].mcu_command_table_field = 2;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_TRAY_CONSUMPTION].callback = CProtocal_handle_link_ams_tray_consumption_ack2;
    _this->packet_info[0x2][0x27].mcu_command_table_field = 2;
    _this->packet_info[0x2][0x27].callback = CProtocal_handle_ams_v2_packet; /* part_info_ack_v2 */
    _this->packet_info[0x2][MSG_AMS_V2_AMS_FILAMENT_DRYING].mcu_command_table_field = 2;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_FILAMENT_DRYING].callback = CProtocal_handle_ams_filament_drying;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_FLUSH_PARAM].mcu_command_table_field = 2;
    _this->packet_info[0x2][MSG_AMS_V2_AMS_FLUSH_PARAM].callback = CProtocal_handle_mc_ams_flush_param;
}

/*** Main AMSv2 patch entrypoint ***/

void patch_ams_callbacks() {

#define DO_PATCH(what) \
        uint32_t expect_insns_##what[] = PROLOGUE_##what; \
        if (memcmp((void *)OFS_##what, expect_insns_##what, 12)) { \
            fprintf(stderr, "*** FORWARD DOES NOT HAVE EXPECTED BYTE SEQUENCE.  FIRMWARE HAS CHANGED; YOU MUST UPDATE forward_shim.cpp.\n"); \
            abort(); \
        } \
        mprotect((void *)((long)OFS_##what & ~(sysconf(_SC_PAGESIZE) - 1)), sysconf(_SC_PAGESIZE), PROT_READ | PROT_WRITE | PROT_EXEC); \
        ((uint32_t *)OFS_##what)[0] = 0xE59Ff000; /* ldr pc, [pc] */ \
        ((uint32_t *)OFS_##what)[2] = (uint32_t)what##_override;
    
    DO_PATCH(CProtocal_setup_callbacks)
    DO_PATCH(CProtocal_send_mcu_packet)
    DO_PATCH(update_ams_object_with_flags)
    DO_PATCH(handle_print_dds_message)

    mprotect((void *)((long)OFS_handle_print_dds_message_limit_target & ~(sysconf(_SC_PAGESIZE) - 1)), sysconf(_SC_PAGESIZE), PROT_READ | PROT_WRITE | PROT_EXEC);
    *(uint32_t *)OFS_handle_print_dds_message_limit_target = 0x135b0801; // patch maximum target of ams_change_filament to 0x10000 instead of 0xf
    
    DO_PATCH(replace_next_extruder_filament_temp)
}

/*** DBus patches ***/

// annoyingly, we cannot just get this from dlfcn.h, because glibc version bad
# define RTLD_NEXT      ((void *) -1l)
extern
#ifdef __cplusplus
"C"
#endif
void *dlsym(void *handle, const char *symbol);

#define SWIZZLE(rtype, name, ...) \
    EXTERN_C rtype name(__VA_ARGS__) { \
        rtype (*next)(__VA_ARGS__) = (rtype(*)(__VA_ARGS__))dlsym(RTLD_NEXT, #name);

typedef struct DBusError {
    const char *name;
    const char *message;
    unsigned int dummy1:1;
    unsigned int dummy2:1;
    unsigned int dummy3:1;
    unsigned int dummy4:1;
    unsigned int dummy5:1;
    void *padding1;
} DBusError;

typedef struct DBusConnection DBusConnection;
typedef struct DBusMessage DBusMessage;

extern "C" void dbus_error_init(DBusError *e);
extern "C" void dbus_error_free(DBusError *e);
extern "C" DBusConnection *dbus_bus_get(int type, DBusError *e);
extern "C" const char *dbus_bus_get_unique_name(DBusConnection *c);
extern "C" DBusMessage *dbus_message_new_signal(const char *path, const char *iface, const char *name);
extern "C" void dbus_message_unref(DBusMessage *msg);
extern "C" bool dbus_connection_send(DBusConnection *c, DBusMessage *msg, uint32_t *serial);
extern "C" bool dbus_message_append_args(DBusMessage *msg, int first_arg_type, ...);
extern "C" void dbus_connection_flush(DBusConnection *c);
extern "C" bool dbus_threads_init_default();

static DBusConnection *_dbus_connection = NULL;

static void _publish_dbus_signal(const char *name, const char *bytes, int len) {
    if (!_dbus_connection) {
        DBusError e;
        dbus_threads_init_default();
        dbus_error_init(&e);
        _dbus_connection = dbus_bus_get(1 /* DBUS_BUS_SYSTEM */, &e);
        if (!_dbus_connection) {
            PRINTF_BLUE("forward_shim: failed to connect to dbus: %s\n", e.message);
            dbus_error_free(&e);
            return;
        }
        PRINTF_BLUE("forward_shim: connected to dbus (I am %s)\n", dbus_bus_get_unique_name(_dbus_connection));
    }
    
    DBusMessage *msg = dbus_message_new_signal("/x1plus/forward", "x1plus.forward.mc", name);
    if (bytes) {
        dbus_message_append_args(msg, (int) 'a' /* DBUS_TYPE_ARRAY */, (int) 'y' /* DBUS_TYPE_BYTE */, &bytes, len, (int) '\0' /* DBUS_TYPE_INVALID */);
    }
    dbus_connection_send(_dbus_connection, msg, NULL);
    dbus_message_unref(msg);
}

static int ttyS1_fd = -1;

SWIZZLE(int, open64, const char *s, int flag, ...)
    va_list ap;
    va_start(ap, flag);
    int mode = va_arg(ap, int);
    va_end(ap);

    int fd = next(s, flag, mode);
    if (!strcmp(s, "/dev/ttyS1")) {
        PRINTF_BLUE("forward_shim: opened /dev/ttyS1 as %d\n", fd);
        _publish_dbus_signal("SerialPortOpened", NULL, 0);
        ttyS1_fd = fd;
    }
    return fd;
}

static uint8_t sp_read_buf[1024];
static size_t  sp_read_pos = 0;

/* this gets very spammy otherwise, so buffer things up into a handful at a time */
static void did_read_n(void *buf, size_t rv) {
    int pos = 0;
    int rem = rv;
    while (rem) {
        int n = sizeof(sp_read_buf) - sp_read_pos;
        if (n > rem)
            n = rem;
        memcpy(sp_read_buf + sp_read_pos, (const char *)buf + pos, n);
        rem -= n;
        pos += n;
        sp_read_pos += n;
        if (sp_read_pos == sizeof(sp_read_buf)) {
            _publish_dbus_signal("SerialPortRead", (const char *) sp_read_buf, sizeof(sp_read_buf));
            sp_read_pos = 0;
        }
    }
}

/* XXX: sometimes we still manage to lose a read or two under heavy load,
 * like around print starting?  but apparently it's not just us, but forward
 * also does.  hope the MC retransmits I suppose */
SWIZZLE(ssize_t, read, int fd, void *buf, size_t count)
    int rv = next(fd, buf, count);
    if (fd == ttyS1_fd) {
        did_read_n(buf, rv);
    }
    return rv;
}

SWIZZLE(ssize_t, write, int fd, const void *buf, size_t count)
    if (fd == ttyS1_fd) {
        _publish_dbus_signal("SerialPortWrite", (const char *) buf, count);
        dbus_connection_flush(_dbus_connection);
    }
    return next(fd, buf, count);
}

extern std::vector<std::string> eth_list;

extern "C" int bbl_sal_get_debug_flag(int a) {
    return 0;
}

extern "C" void __attribute__ ((constructor)) init() {
    unsetenv("LD_PRELOAD");
    for (auto s : eth_list ) {
        PRINTF_BLUE("forward_shim: adding to network list, started with %s\n", s.c_str());
    }
    eth_list.push_back("eth0");
    patch_ams_callbacks();
}
