# AMS compatibility investigation and validation

Source baseline: upstream `main`, `09dd052ff3c9cf24b761645e80759e714b796a8f`
(2026-10-23 inspection). This investigation covers three AMS 2 Pro units for
spool failover, with mixed generations and AMS HT as secondary cases.

## Existing implementation

[PR #547](https://github.com/X1Plus/X1Plus/pull/547) merged May 31, 2026.
Its changes are already on main. The supplied historical commit `9c664569`
is the legacy MC fallback at the end of that series. Four subsequent main
commits concern temperature graphs, USB browsing and Polar Cloud; none modify
`forward_shim.cpp`. The current implementation is substantially more than
device recognition:

| Layer / source | Verified source behavior | Verification limit |
| --- | --- | --- |
| `installer/base.json` | Selects MC 00.00.32.89 and hardware-specific AMS images; legacy MC option exists | Build selection is not proof of device compatibility |
| `bbl_screen-patch/forward_shim.cpp` | Bridges old proprietary `forward` to new MC AMSv2 protocol; four logical AMS slots | OEM internal state machine and MC source unavailable |
| `CProtocal_handle_ams_v2_ams_info_update` | Two-pass discovery and status synthesis; normal AMS IDs 0..3, HT IDs 0x80..0x8f mapped into free logical slots | At most four units total represented by this shim, regardless of physical MC capacity |
| `CProtocal_handle_get_version` | Caches `AMS`, `N3F` (AMS 2 Pro), `N3S` (HT), or `UNKNOWN` based on hardware prefix | Host report tests do not exercise this callback or firmware version parsing |
| `CProtocal_send_mcu_packet_override` | Rewrites tray requests, version/SN queries, consumption and routing commands; HT destination 0x1800, normal AMS 0x0700 | Not a verified complete firmware-update transport |
| `handle_print_dds_message_override` | Converts load/unload targets, M620 addressing, external-spool and print mappings; implements drying request/response handling | No hardware actuation performed |
| `CProtocal_handle_ams_tray_info_read` | Preserves material type in sidecar cache for flush cooling-temperature lookup | RFID acquisition itself belongs to OEM/AMS components |
| `update_ams_object_with_flags_override_C` | Adds humidity, temperature, adapter status and estimated drying time; renders HT as one tray | Drying completion estimate is lost on forward restart |
| `bbl_screen-patch/interpose.cpp::rewrite_print_for_amsht` | Converts public HT status back into legacy screen IDs/bitmaps; JavaScript receives unmodified status | Requires OEM UI for integration validation |
| `qml/printer/FilamentPad.qml.patch`, `FilamentPage.qml.patch`, `FilamentHumidityPopupDryable.qml` | HT presentation, humidity/drying UI and loading/rotation restrictions | QML rendering and controls NOT RUN |
| `qml/settings/VersionPage.qml`, `VersionDialog.qml`, `UpgradeDialog.qml` | Hardware-specific image availability, names and update selection; sends `module: ams`, numeric `submodule` | UI selection alone does not prove physical flash destination |
| `x1plus/services/x1plusd/mqtt.py::MQTTClient` | Preserves AMS status when a push omits AMS; dispatches requests/reports | No dedicated failover implementation found here |
| `x1plus/services/x1plusd/mcproto.py`, `scripts/dissector_mcproto.lua` | Serial diagnostics and protocol interpretation | Some protocol semantics remain reverse-engineering notes |
| `bbl_screen-patch/upgrade_shim.cpp` | Replaces embedded module description JSON to recognize N3F/N3S | Does not expose proprietary updater implementation |

The Python paths above are under
`images/cfw/opt/x1plus/lib/python/`. QML paths are under
`bbl_screen-patch/patches/printerui/`. Original X1Plus code is Apache-2.0;
subcomponents retain their respective licenses. No extracted OEM binaries or
device data are part of this change.

The load/unload and print routing path ends in MC/AMS commands. Automatic
failover appears to depend on the existing OEM forward/MC/AMS stack and slicer
settings; the precise division inside proprietary components is **unverified**.
No application-level replacement failover logic is introduced.

## Historical reports and current evidence

* [#407](https://github.com/X1Plus/X1Plus/issues/407) remains open but includes
  confirmations that original AMS units 1–4 update in 3.1. A later AMS2 report
  predates #547. It does not establish that the original bug remains current.
* [#507](https://github.com/X1Plus/X1Plus/pull/507), merged July 14, 2025,
  adds secondary AMS `submodule` selection and changes recommended firmware.
* [#505](https://github.com/X1Plus/X1Plus/issues/505) and
  [#518](https://github.com/X1Plus/X1Plus/issues/518) are closed historical
  unsupported-hardware reports. #518 describes X1Plus 3.0 and old MC firmware.
* [Discussion #460](https://github.com/X1Plus/X1Plus/discussions/460) asks
  about feasibility; [#461](https://github.com/X1Plus/X1Plus/discussions/461)
  tracks the broader request. #547 supplies the later implementation.
* [#552](https://github.com/X1Plus/X1Plus/issues/552) reports missing material
  data on three of four units, but was filed before #547. A maintainer
  recommended testing #547. **No reproduced connection to this parser defect.**
* [#563](https://github.com/X1Plus/X1Plus/issues/563) reports invalid tray ID
  during HT flow calibration on 3.1-17 with new MC. Still a separate open issue;
  this change does not claim to repair calibration routing.

## Prioritized defect and capability matrix

| Priority | Finding | Evidence class | Disposition |
| --- | --- | --- | --- |
| P1 | Short AMSv2 records can read beyond packet allocation | Reproduced in production handler under ASan at baseline line 890 using `{0,0}` | Fixed: validate complete report before state changes |
| P1 | Slot >=4 can address another AMS's tray bits; large values cause undefined shifts | Source plus deterministic regression assertions | Fixed: reject slots outside 0..3 |
| P1 | Malformed suffix can leave new physical mapping/environment without published report | Source plus state-snapshot regression | Fixed: all validation precedes mutation |
| P2 | HT reread acknowledgement path builds reread using physical ID then calls a logical-to-physical send path | Source observation in `CProtocal_handle_ams_tray_info_write` | Follow-up: mock nonidentity mappings; no fix claimed |
| P2 | Disconnected sidecar entries can remain in `ams_info`; lookup has no active mask | Source observation; public disconnect status tested separately | Follow-up: establish full-report vs incremental guarantees and stale-response policy |
| P2 | Drying guard uses `!mc_spoke_new_protocol` (function address) instead of protocol state | Verified source expression; control path not run | Follow-up with mocked command handler; no change in this slice |
| P2 | Actual firmware update destination through OEM updater | Partial source trace only | All flashing NOT RUN; requires read-only transport capture and mocks first |
| P2 | Three AMS2 physical spool failover | No printer execution | NOT RUN; use procedure below |
| P3 | Flush parameter type 0 and auto-stop drying | Explicit TODO / fallback in source | Incomplete; no guessed protocol commands |
| P3 | Unknown model JSON fallback currently resembles original AMS | Source observation; host tests preserve UNKNOWN cache only | Capability semantics need separate tests |

Rejected unknown TLV types already prevented report publication before this
change; they now leave prior state intact. Known records with additional
trailing fields remain accepted. Empty reports still synthesize disconnection.
This does not add comprehensive validation to other packet handlers.

## Automated validation

Run `python3 bbl_screen-patch/tests/run_forward_ams_tests.py --sanitize`.
The runner compiles unmodified production source sections, with mocked packet
envelope, logging and legacy callback. See [test details](../bbl_screen-patch/tests/README.md).
GitHub workflow `forward-ams-tests.yml` runs the same ASan/UBSan checks and
compiles the complete shim for ARM. These checks require no OEM key.

| Configuration | Automated coverage | Physical / integration status |
| --- | --- | --- |
| One original AMS | Legacy callback and valid report preserve model cache | NOT RUN |
| One AMS2 Pro | Valid report preserves preseeded N3F cache | Actual model discovery NOT RUN |
| Three AMS2 units | IDs, reordered records, 12 tray bits, distinct humidity/temperature | Physical addressing NOT RUN |
| Mixed generations / HT | Physical namespaces, remapping, four-slot capacity | Model/version callback and drying NOT RUN |
| Disconnection / reconnection | Empty report clears published presence; next report restores IDs | Sidecar stale cleanup is not fixed |
| Unknown firmware | Known trailing fields accepted; UNKNOWN cache retained | Firmware compatibility NOT RUN |
| Invalid telemetry | Short/invalid records, invalid suffix, no state mutation, recovery | Real transport framing NOT RUN |
| Spool failover | No failover simulation claimed | Routing and physical runout NOT RUN |

A complete `.x1p` build additionally needs OEM firmware/decryption material.
The host harness and ARM compilation do not prove a distributable image or
runtime compatibility with proprietary components.

## Three-unit physical validation plan — NOT RUN

This is a procedure for a separately authorized hardware session. Do not
perform firmware updates as part of it. Record the tested X1Plus commit and
existing AP/MC/AMS firmware/hardware versions before testing; redact serials
and network/private metadata before committing diagnostic fixtures.

1. With the printer idle, record each unit's physical label, reported physical
   ID, logical ID, hardware prefix and all four slot identities. Expected:
   three unique AMS IDs, twelve distinct slots, no cross-unit material changes.
2. Compare screen, read-only MQTT status and serial diagnostics for presence,
   RFID/material type, current/target/previous tray and environmental values.
   Expected: all three surfaces identify the same unit and slot. Record raw
   fields where interpretation differs rather than guessing their meaning.
3. After safe shutdown, disconnect one unit according to the manufacturer's
   instructions, restart and observe. Expected: absent unit's published trays
   disappear; other units remain correct. Reconnect after safe shutdown and
   repeat. Do not unplug live buses. Verify IDs after full restart too.
4. Once actuation is explicitly authorized, load/unload one known spool from
   each unit and verify the physical route against reported target/current
   tray. Stop on mismatched motion, unexpected feeding or a persistent error.
5. Enable the existing printer/slicer automatic refill option. Use compatible
   identical material/color settings, a deliberately short starting spool and
   reserve spools on the other units. In a supervised small print, observe
   actual runout and two successive transfers across units. Expected: correct
   reserve selection, no simultaneous feeding, no wrong-unit actuation, correct
   current/previous/target status and completed print. Repeat with a different
   starting unit and record eligibility rules actually observed.
6. Test a mixed original AMS/AMS2 arrangement separately. Test HT detection,
   material reads and physical mapping separately before any authorized drying
   test. Heating requires supervision, correct external power and manufacturer
   limits. No drying command or temperature is inferred by this investigation.
7. Firmware targeting remains read-only: correlate UI submodule, module table,
   packet destination and physical ID using captured queries/mocked commands.
   Do not launch a real upgrade to prove selection.

Next engineering step: validate report/update framing and HT reread address
conversion with mocked nonidentity mappings, then collect sanitized status
from the three-unit setup before attributing physical failures to software.
