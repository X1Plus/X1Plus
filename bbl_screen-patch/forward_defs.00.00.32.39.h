#ifndef FIRMWARE_00_00_32_39
#  error these definitions are not for you, buster
#endif

#  define OFS_CProtocal_setup_callbacks 0xa6210
__attribute__((naked)) void CProtocal_setup_callbacks_override() {
    asm volatile(
        "stmdb sp!,{r0,lr}\n"
        "bl 1f\n"
        "ldmia sp!,{r0,lr}\n"
        "b CProtocal_setup_callbacks_override_C\n"
        "1:\n"
        "stmdb sp!, {r4, r5, r6, r7, r8, lr}\n"
        "mov r4, r0\n"
        "add r0, r0, #0x2580\n"
        "ldr r5, =%c0\n"
        "bx r5\n"
        ".ltorg\n"
    : : "X"(OFS_CProtocal_setup_callbacks+12));
}
#define PROLOGUE_CProtocal_setup_callbacks {0xe92d41f0, 0xe1a04000, 0xe2800d96}

#  define OFS_CProtocal_send_mcu_packet 0xa9f60
__attribute__((naked)) int CProtocal_send_mcu_packet_orig(CProtocal *_this, void *payload, size_t payload_length, uint32_t req, uint32_t dest, uint32_t src, uint32_t msg_id, uint32_t msg_class, uint32_t param_8) {
    asm volatile(
        "stmdb sp!,{r4,r5,r6,r7,r8,r9,r10,r11,lr}\n"
        "sub sp, sp, #0x224\n"
        "mov r7, r2\n"
        "ldr r4,=%c0\n"
        "bx r4\n"
        ".ltorg\n"
    : : "X"(OFS_CProtocal_send_mcu_packet+12));
}
#define PROLOGUE_CProtocal_send_mcu_packet {0xe92d4ff0, 0xe24ddf89, 0xe1a07002}

#  define OFS_update_ams_object_with_flags 0xcbf50
__attribute__((naked)) void update_ams_object_with_flags_override() {
    asm volatile(
        "stmdb sp!,{r0,r1,r2,lr}\n"
        "bl 1f\n"
        "ldmia sp!,{r0,r1,r2,lr}\n"
        "b update_ams_object_with_flags_override_C\n"
        "1:\n"
        "stmdb sp!,{r4,r5,r6,r7,r8,r9,r10,r11,lr}\n"
        "movw r9,#0x3dd8\n"
        "movt r9,#0x14\n"
        "ldr pc,=%c0\n"
        ".ltorg\n"
    : : "X"(OFS_update_ams_object_with_flags+12));
}
#define PROLOGUE_update_ams_object_with_flags {0xe92d4ff0, 0xe3039dd8, 0xe3409014}

#  define OFS_handle_print_dds_message 0x708fc
__attribute__((naked)) int handle_print_dds_message_orig(CGparser *p, json &j, int param3) {
    asm volatile(
        "stmdb sp!,{r4, r5, r6, r7, lr}\n"
        "mov r4, r0\n"
        "ldr r0, [r0,#0x7f4]\n"
        "ldr pc,=%c0\n"
        ".ltorg\n"
    : : "X"(OFS_handle_print_dds_message+12));
}
#define PROLOGUE_handle_print_dds_message {0xe92d40f0, 0xe1a04000, 0xe59007f4}

#  define OFS_handle_print_dds_message_limit_target 0x7e29c

#  define OFS_replace_next_extruder_filament_temp 0x7d388
__attribute__((naked)) void *replace_next_extruder_filament_temp_orig(std::string &path, void *b, std::string &next_extruder, std::string &new_temp) {
    asm volatile(
        "stmdb sp!,{r4, r5, r6, r7, r8, r9, r10, r11, lr}\n"
        "movw r11, #0x3dd8\n"
        "movt r11, #0x14\n"
        "ldr pc,=%c0\n"
        ".ltorg\n"
    : : "X"(OFS_replace_next_extruder_filament_temp+12));
}
#define PROLOGUE_replace_next_extruder_filament_temp {0xe92d4ff0, 0xe303bdd8, 0xe340b014}

struct CProtocal;

struct packet_message_t {
    int (*callback)(CProtocal *);
    uint8_t mcu_command_table_field; /* Created by retype action */
    uint8_t field2_0x5;
    uint8_t field3_0x6;
    uint8_t field4_0x7;
    uint8_t cmd_count_done; /* Created by retype action */
    uint8_t field6_0x9;
    uint8_t field7_0xa;
    uint8_t field8_0xb;
    int cmd_count_drop; /* Created by retype action */
    int cmd_count_send; /* Created by retype action */
    uint8_t cmd_mtc; /* Created by retype action */
    uint8_t field12_0x15;
    uint8_t field13_0x16;
    uint8_t field14_0x17;
    uint8_t cmd_count_doing; /* Created by retype action */
    uint8_t field16_0x19;
    uint8_t field17_0x1a;
    uint8_t field18_0x1b;
    uint8_t us_at_string; /* Created by retype action */
    uint8_t field20_0x1d;
    uint8_t field21_0x1e;
    uint8_t field22_0x1f;
    uint8_t field23_0x20;
    uint8_t field24_0x21;
    uint8_t field25_0x22;
    uint8_t field26_0x23;
    uint8_t field27_0x24;
    uint8_t field28_0x25;
    uint8_t field29_0x26;
    uint8_t field30_0x27;
    uint8_t field31_0x28;
    uint8_t field32_0x29;
    uint8_t field33_0x2a;
    uint8_t field34_0x2b;
    uint8_t field35_0x2c;
    uint8_t field36_0x2d;
    uint8_t field37_0x2e;
    uint8_t field38_0x2f;
    uint8_t field39_0x30;
    uint8_t field40_0x31;
    uint8_t field41_0x32;
    uint8_t field42_0x33;
};

struct __attribute__((packed)) bus_command_packet {
    uint8_t start_marker; // 0
    uint8_t flags; // 1
    uint16_t sequence_num; // 2
    uint16_t packet_length; // 4
    uint8_t header_crc8; // 6
    uint16_t dest_addr; // 7
    uint16_t src_addr; // 9
    uint8_t cmd_id; // 11
    uint8_t cmd_set; // 12
    uint8_t *payload;
};

struct CGparser {
    char _dummy[0x5F8];
    bool use_ams;
    char _dummy2[0x1CF];
    CProtocal *protocal;
};
static_assert(offsetof(struct CGparser, use_ams) == 0x5f8);
static_assert(offsetof(struct CGparser, protocal) == 0x7c8);

struct CProtocal {
    char _dummy[0x58];
    union {
        char _dummy2[0x2558];
        struct CGparser gparser;
    };
    packet_message_t packet_info[5][255];
    bus_command_packet *packet;
};
static_assert(offsetof(struct CProtocal, gparser) == 0x58);
static_assert(offsetof(struct CProtocal, packet_info) == 0x25b0);

void (*CGparser_publish_json)(CGparser *, json &, int) = (void(*)(CGparser *, json&, int))0x6aaf0;
