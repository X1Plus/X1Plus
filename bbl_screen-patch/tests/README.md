# AMS report handler regression tests

Run on a Linux host with Python 3 and g++:

```sh
python3 bbl_screen-patch/tests/run_forward_ams_tests.py --sanitize
# Or, from bbl_screen-patch:
make test-forward-ams
```

`CXX` selects another host C++ compiler. `--source /path/to/forward_shim.cpp`
tests a different source revision. The runner extracts complete, unmodified
production sections (AMS state/mapping and report callbacks) and compiles them
with a mock packet envelope, logger and legacy report callback. It does not
compile or execute the ARM trampolines, load OEM binaries, publish MQTT, or
connect to hardware. Temporary build files are removed automatically.

Fixtures are synthetic records based on the layouts already interpreted by
`CProtocal_handle_ams_v2_ams_info_update`, not device captures. Checks cover:

* Original AMS protocol callback and single-unit report behavior.
* One and three AMS2 units, reordered descriptors, distinct environmental
  values and all twelve tray bits.
* Mixed physical AMS/HT address spaces, capacity limits and unknown cached
  hardware type (no guessed model).
* Report-level disconnect/reconnect, unchanged-report suppression and rereads.
* Short known records, invalid physical IDs and slots, malformed TLV envelopes,
  packet lengths below the framing overhead and invalid suffixes after valid
  records. Rejected reports preserve cached state and pending rereads.
* Valid reports after invalid telemetry, trailing fields in known records and
  the uninterpreted extruder record.

ASan reproduces an out-of-bounds read on upstream `09dd052ff3c9cf24b761645e80759e714b796a8f`
with `{0, 0}` (an AMS descriptor with a zero-byte body). The outer TLV length
was accepted before reading `ams_id` beyond the buffer. Invalid tray slots can
also set a neighboring AMS's bits or cause an oversized shift. A valid prefix
followed by malformed data could mutate mapping/environmental state without
publishing a report. The complete-report validation prevents all three cases.

These checks do **not** prove hardware compatibility, firmware destination,
model/version discovery, MQTT/UI integration, or spool failover. See
[the investigation and physical validation plan](../../docs/ams-compatibility.md).
