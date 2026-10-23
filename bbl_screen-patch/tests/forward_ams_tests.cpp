#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <vector>
#include <stdlib.h>

struct Packet {
    int packet_length;
    uint8_t *payload;
};
struct CProtocal { Packet *packet; };
static bool mc_speaks_new_protocol;
static void mc_spoke_new_protocol() { mc_speaks_new_protocol = true; }
static void mc_spoke_old_protocol() { mc_speaks_new_protocol = false; }
static void x1plus_logf(const char *, ...) {}

#include "forward_ams_under_test.inc"

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); exit(1); \
} } while (0)

static link_ams_report observed;
static int reports;
static int capture(CProtocal *protocol) {
    CHECK(protocol->packet->packet_length == 15 + sizeof(observed));
    memcpy(&observed, protocol->packet->payload, sizeof(observed));
    ++reports;
    return 0;
}
static void reset() {
    memset(ams_info, 0, sizeof(ams_info));
    memset(&prev_synth_link_ams_report, 0, sizeof(prev_synth_link_ams_report));
    memset(&observed, 0, sizeof(observed));
    force_ams_reread = 0;
    mc_speaks_new_protocol = false;
    reports = 0;
    CProtocal_original_ams_report = capture;
}
typedef std::vector<uint8_t> Bytes;
static void append(Bytes &to, const Bytes &from) { to.insert(to.end(), from.begin(), from.end()); }
static Bytes unit(uint8_t id, uint16_t temperature = 521, uint8_t humidity = 25) {
    return {0, 10, id, uint8_t(temperature), uint8_t(temperature >> 8), 0, 0, humidity, 0, 2, 1, 4};
}
static Bytes tray(uint8_t id, uint8_t slot, uint8_t status = 5) { return {1, 3, id, slot, status}; }
static void deliver(Bytes bytes, int length_override = -1) {
    // Allocate exactly the payload length so ASan catches reads across its end.
    uint8_t *payload = new uint8_t[bytes.size()];
    if (!bytes.empty()) memcpy(payload, bytes.data(), bytes.size());
    Packet packet = {length_override == -1 ? int(15 + bytes.size()) : length_override, payload};
    const int length = packet.packet_length;
    CProtocal protocol = {&packet};
    CHECK(CProtocal_handle_ams_v2_ams_info_update(&protocol) == 0);
    CHECK(packet.payload == payload);
    CHECK(packet.packet_length == length);
    if (!bytes.empty()) CHECK(!memcmp(payload, bytes.data(), bytes.size()));
    delete[] payload;
}
static void unchanged_after(const Bytes &invalid, int length_override = -1) {
    struct ams_info before[4];
    memcpy(before, ams_info, sizeof(before));
    const link_ams_report previous = prev_synth_link_ams_report;
    const bool protocol_before = mc_speaks_new_protocol;
    const uint32_t reread_before = force_ams_reread;
    const int count = reports;
    deliver(invalid, length_override);
    CHECK(!memcmp(before, ams_info, sizeof(before)));
    CHECK(!memcmp(&previous, &prev_synth_link_ams_report, sizeof(previous)));
    CHECK(mc_speaks_new_protocol == protocol_before);
    CHECK(force_ams_reread == reread_before);
    CHECK(reports == count);
}
static Bytes three_units() {
    Bytes bytes;
    // Deliberately reorder physical IDs and put trays before AMS descriptors.
    for (uint8_t id : {2, 0, 1}) {
        for (uint8_t slot = 0; slot < 4; ++slot) append(bytes, tray(id, slot));
        append(bytes, unit(id, 500 + id, 20 + id));
    }
    append(bytes, {2, 1, 3});
    return bytes;
}
static void test_valid_reports() {
    reset();
    deliver(three_units());
    CHECK(reports == 1 && observed.ams_exist == 7);
    CHECK(observed.tray_exist == 0xfff && observed.tray_read_done == 0xfff);
    CHECK(observed.tray_is_bbl == 0xfff && observed.tray_reading == 0);
    CHECK(observed.insert_poweron_remain == 3);
    for (int id = 0; id < 3; ++id) {
        CHECK(ams_phys_to_log(id) == id);
        CHECK(ams_info[id].temp_dC == 500 + id);
        CHECK(ams_info[id].humidity == 20 + id);
    }
    deliver(three_units());
    CHECK(reports == 1); // Unchanged report suppression is preserved.
    deliver({});
    CHECK(reports == 2 && observed.ams_exist == 0 && observed.tray_exist == 0);
    deliver(three_units());
    CHECK(reports == 3 && observed.ams_exist == 7);
    puts("PASS three units: reordered discovery, tray state, disconnect/reconnect");

    reset();
    ams_info[0].hw_type = AMS;
    Bytes single = unit(0);
    append(single, tray(0, 3, 2));
    deliver(single);
    CHECK(observed.ams_exist == 1 && observed.tray_reading == 8);
    CHECK(ams_info[0].hw_type == AMS);
    // The legacy packet callback still selects the old protocol.
    Packet packet = {0, nullptr};
    CProtocal protocol = {&packet};
    CProtocal_original_ams_report = [](CProtocal *) { return 23; };
    CHECK(CProtocal_handle_ams_report(&protocol) == 23);
    CHECK(!mc_speaks_new_protocol);
    puts("PASS single original AMS and legacy callback");

    reset();
    ams_info[0].hw_type = N3F;
    deliver(single);
    CHECK(observed.ams_exist == 1 && ams_info[0].hw_type == N3F);
    puts("PASS single AMS2 Pro retains known model");

    reset();
    Bytes mixed = unit(0x8f);
    append(mixed, tray(0x8f, 0));
    append(mixed, unit(2));
    append(mixed, tray(2, 3));
    deliver(mixed);
    CHECK(ams_phys_to_log(0x8f) == 0 && ams_phys_to_log(2) == 2);
    CHECK(observed.ams_exist == 5 && observed.tray_exist == 0x801);
    CHECK(ams_info[0].hw_type == UNKNOWN); // Status does not guess hardware revision.
    puts("PASS mixed AMS/HT physical namespaces and unknown model fallback");

    reset();
    Bytes extended = unit(0);
    extended[1] += 2;
    append(extended, {0xaa, 0xbb});
    append(extended, {3, 0}); // Known, uninterpreted extruder record.
    append(extended, tray(0, 0));
    deliver(extended);
    CHECK(observed.ams_exist == 1 && observed.tray_exist == 1);
    puts("PASS known records with new trailing fields and extruder record");

    reset();
    Bytes capacity = three_units();
    append(capacity, unit(3));
    append(capacity, tray(3, 3));
    append(capacity, unit(0x80));
    append(capacity, tray(0x80, 0));
    deliver(capacity);
    CHECK(observed.ams_exist == 0xf && observed.tray_exist == 0x8fff);
    CHECK(ams_phys_to_log(0x80) == 0xff);
    puts("PASS four-slot capacity does not alias excess HT onto another unit");
}
static void test_invalid_reports() {
    reset();
    unchanged_after({0, 0});
    CHECK(!mc_speaks_new_protocol);
    deliver(three_units());
    force_ams_reread = 0x10;
    // Invalid slots must never set another unit's tray bits or shift by >=32.
    for (uint8_t slot : {4, 16, 32, 255}) {
        Bytes bad = unit(0);
        append(bad, tray(0, slot));
        unchanged_after(bad);
    }
    puts("PASS invalid tray slots cannot contaminate neighboring AMS state");
    // Every truncated form of each known fixed-size record, even with a
    // consistent TLV outer length, must be rejected before reading fields.
    for (Bytes record : {unit(0), tray(0, 0), Bytes{2, 1, 1}}) {
        for (size_t size = 2; size < record.size(); ++size) {
            Bytes truncated(record.begin(), record.begin() + size);
            truncated[1] = size - 2;
            unchanged_after(truncated);
        }
    }
    puts("PASS short AMS/tray/flag records");
    for (uint8_t id : {4, 127, 144, 255}) {
        unchanged_after(unit(id));
        unchanged_after(tray(id, 0));
    }
    unchanged_after({0});
    unchanged_after({0, 255, 0});
    unchanged_after({}, 14);
    puts("PASS invalid device IDs, TLV envelopes and packet lengths");

    // A valid prefix must not change cached mapping/environment on rejection.
    for (Bytes suffix : {Bytes{0}, Bytes{2, 0}, Bytes{4, 0}, tray(0, 255), unit(144)}) {
        Bytes prefix = unit(0x80, 999, 99);
        append(prefix, unit(1, 998, 98));
        append(prefix, suffix);
        unchanged_after(prefix);
    }
    puts("PASS malformed suffix rejection preserves full prior state and pending reread");
    deliver(three_units());
    CHECK(force_ams_reread == 0);
    CHECK(reports == 2);
    CHECK(observed.tray_is_bbl == (0xfff & ~0x10));
    puts("PASS recovery after invalid telemetry and pending reread");
}
int main() {
    test_valid_reports();
    test_invalid_reports();
    puts("All AMS report regression checks passed.");
}
