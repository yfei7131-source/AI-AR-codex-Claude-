# EVT-1 H02 Footprint Convergence & H03 Real PCB Layout Verification (`NOT FOR FAB`)

> **Baseline**: PR #39 (`hardware/evt1-h02-reve-h03-bridge-20261120` @ `ce1f02a4`)
> **Target EDA**: Live **EasyEDA Pro V4.1.97** (`easyeda-agent v1.17.0`)
> **Manufacturing Status**: **`NOT FOR FAB` (BLOCKED)** — see [`BLOCKED.md`](./BLOCKED.md).

## Executive Summary

This delivery executes two strictly separated, live EasyEDA Pro V4.1.97 tracks without overwriting PR #39 or the `22.0 × 4.2 mm` bridge baseline:

1. **Track A — H02 Footprint Convergence & BOM/PCB Attribute Hygiene (`22.0 × 4.2 mm` Preserved)**:
   - Converged **`112 → 9`** `MISSFOOTPRINT` items across all 3 boards (**`103`** OEM/IPC footprints newly bound: `45` Main / `25` Bridge / `33` Audio, including `Nordic nRF5340-CMAA WLCSP95`, `Hirose BM28 30+2P / 16+2P`, `ROHM SOD-523`, `Epson FA-128`, `Johanson 2450AT18B100E`, IPC passives, and EVT-1 test points).
   - Cleaned attributes on `11` `#FLG*` (`Add into BOM=no, Convert to PCB=no`), `3` DNP RF shunts (`BOM=no, PCB=yes`), `4` off-board parts (`BAT1`/`SPK1` ×2, `BOM=yes, PCB=no`), and `3` NDA-DNP optical parts (`BOM=no`).
   - **Live 3-board strict ERC**: **`268 (PR #36) → 246 (PR #38) → 130 (PR #39) → 27`** (`18 ONLYSYMBOL` sheet boxes + `9` genuinely NDA/TBD/Off-board `MISSFOOTPRINT`, **`0` electrical errors / `0` warnings**).
   - **Exact Rev E Netlist Parity**: All **`207`** net groups (`M-MAIN-L`, `M-OPT-BRIDGE`, `M-AUD-R`) and all Rev E ECOs (`ECO-02`, `ECO-03`, `ECO-07`, `ECO-08`, `ECO-09`, `ECO-14`) verified bit-for-bit identical to PR #39.
   - **Baseline `22.0 × 4.2 mm` `PCB2` Strictly Preserved**: `17` placed parts, `0` MK2 errors, `0` clearance errors.

2. **Track B — Independent `MECR-01` `25.0 × 4.6 mm` Full 86-Part Bridge Layout + Live 4-Layer Copper Routing**:
   - **Complete `86 / 86` bridge placement** (`TOP=37, BOT=49`, `328` physical pads, `86/86` UniqueIDs + `86/86` hierarchical Channel IDs matched with `0` diffs against live `.enet`).
   - **Pre-Route Live Strict DRC**: **`0` clearance errors** (`0` Board Outline, `0` MK2 Slot, `0` Pad-to-Pad, `0` Short), `308` airwires (`306` SMD Pad + `2` Plane Zone), `1` EasyEDA headless `Import Changes`.
   - **Live 4-Layer Copper Routing (`TOP/L3/L4/BOT`)**: Committed **`185` real tracks + `45` real `4/8 mil` HDI vias** (`0` CLI failures), including `29` `GND` vias stitching `TOP`/`BOT` to `L2`/`L5` internal `GND` planes (`Plane Zone` errors **`2 → 0`**; `SMD Pad` airwires **`306 → 251`**, `-55` real connections verified by live EasyEDA Pro V4.1.97 DRC; `MK2` remains **`0`**; **`0`** clearance errors across `85/86` components).

## Deliverable Inventory

| Artifact | Purpose |
| :--- | :--- |
| [`native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2`](./native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2) | Track A editable native EasyEDA Pro V4.1.97 archive (103 OEM footprints converged, `22.0 × 4.2 mm` preserved) |
| [`native/ZY_AIAR_EVT1_H03_MECR01_25x4_6_TRIAL_NOT_FOR_FAB.epro2`](./native/ZY_AIAR_EVT1_H03_MECR01_25x4_6_TRIAL_NOT_FOR_FAB.epro2) | Track B independent `MECR-01` `25.0 × 4.6 mm` editable native archive (`86/86` placed, `185` tracks, `45` vias) |
| [`H02_FOOTPRINT_CONVERGENCE.md`](./H02_FOOTPRINT_CONVERGENCE.md) | `112 → 9` `MISSFOOTPRINT` breakdown, OEM footprint specs, and BOM/PCB attribute hygiene |
| [`BRIDGE_22x4_2_VS_25x4_6_COMPARISON.md`](./BRIDGE_22x4_2_VS_25x4_6_COMPARISON.md) | Head-to-head `22.0 × 4.2 mm` vs `25.0 × 4.6 mm` layout, routing, DRC, and `MECR-01` analysis |
| [`BLOCKED.md`](./BLOCKED.md) | Honest `NOT FOR FAB` manufacturing blockers, NDA gates, and remaining DRC/routing closure list |
| [`verification-report.json`](./verification-report.json) | Machine-verifiable Track A & Track B verification receipt |
| [`evidence/track-a-22x4_2/`](./evidence/track-a-22x4_2/) | Raw live EasyEDA Pro V4.1.97 3-board strict ERC, Protel2 netlists, cleaned Rev E.1 BOM CSVs, `22 × 4.2` PCB2 dump & DRC |
| [`evidence/track-b-25x4_6/`](./evidence/track-b-25x4_6/) | Raw live `25 × 4.6` pre/post-route dumps, `pcb-layers.json`, `pcb-drc-rules.json`, pre/post strict DRC, live routing log |
| [`evidence/tests/`](./evidence/tests/) | Local regression test logs (`avdd_safety.log`, `h02_native_unittest.log`, `closure_unittest.log`, `pr39_regression.log`) |
| [`SHA256SUMS.txt`](./SHA256SUMS.txt) | Cryptographic integrity manifest for all deliverables |

## Reproducible Verification Command

```bash
python3 -B hardware/evt1-native-eda-20261118/h02-fp-h03-pcb/verify_h02_fp_h03_pcb.py \
  --root hardware/evt1-native-eda-20261118/h02-fp-h03-pcb \
  --out /tmp/h02-fp-h03-pcb-verify.json
```
