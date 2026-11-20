# EVT-1 H03 3-Board Real PCB Layout & Bridge Live Routing (`NOT FOR FAB`)

> **Baseline**: PR #40 (`hardware/evt1-h02-fp-h03-pcb-20261120` @ `c86ea89`)
> **Target EDA**: Live **EasyEDA Pro V4.1.97** (`easyeda-agent v1.17.0`)
> **Manufacturing Gate**: **`NOT FOR FAB` (BLOCKED)** — see [`BLOCKED.md`](./BLOCKED.md).

## Key Engineering Achievements (100% Live EasyEDA Pro V4.1.97 Verified)

1. **`0` Post-Route Clearance Errors Across ALL THREE BOARDS (`257` Components, `1,074` Pads, `340` Tracks, `59` Vias)**:
   - **`PCB2` (`25.0 × 4.6 mm` MECR-01 Independent Bridge)**: Eliminated **all `71` PR #40 post-route clearance errors (`71 → 0`)** — `64 → 0` L2/L5 Plane Zone via anti-pad errors (via exact SDF-union anti-pad cutouts) and `7 → 0` `MK2` polygon ring errors — while committing **`317` real copper tracks + `28` HDI `4/8 mil` vias** (`6` nets `100%` complete including `clk_48m` via `U2` BGA checkerboard VIPPO, optical QSPI `*_PANEL`, and `SYS_I2C_SCL_1V8`; total strict DRC **`338 → 271`**; `Plane Zone` **`2 → 0`**; `MK2` **`0`**).
   - **`PCB1` (`M-MAIN-L`, `8.2 × 46.0 mm` Stepped Left Temple)**: Placed **`118 / 118`** OEM-bound components (`507` pads), replaced 9 netless footprint-embedded thermal vias on `U1` (`ESP32-S3`) with **9 persisted PCB-level `GND` thermal vias + 10 GND stitch vias**, respected locked 6L RF keepout (`Y=[0,4.2]`) and `MK1` acoustic port → **`0` clearance errors**, **`Plane Zone: 1 → 0`**. `J2` (Camera NDA), `J3` (Pogo TBD), `BAT1`, `SPK1` remain unplaced & `BLOCKED`.
   - **`PCB3` (`M-AUD-R`, `5.2 × 34.0 mm` Right Audio Temple)**: Placed **`53 / 53`** OEM-bound components (`239` pads, including `Nordic nRF5340-CMAA WLCSP95` with Nordic-compliant `0.195 mm` NSMD lands, `Hirose BM28-16+2P`, `FA-128`, `FC-1610AN` ECO-08 crystal, `ANT2`, `TP6` SWD, `MK3`), committed **12 GND L2/L5 stitch vias**, respected locked 6L RF keepout (`Y=[0,4.0]`) and `MK3` acoustic port → **`0` clearance errors**, **`Plane Zone: 2 → 0`**. `BAT1`, `SPK1` remain unplaced & `BLOCKED`.
2. **Baseline `22.0 × 4.2 mm` Strictly Preserved**: PR #40's `h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2` is cryptographically verified unchanged. Zero locked manufacturing rules were relaxed.

## Deliverable Index

| Artifact | Purpose |
| :--- | :--- |
| [`native/ZY_AIAR_EVT1_H03_3BOARD_MECR01_TRIAL_NOT_FOR_FAB.epro2`](./native/ZY_AIAR_EVT1_H03_3BOARD_MECR01_TRIAL_NOT_FOR_FAB.epro2) | Live-exported editable 3-board EasyEDA Pro V4.1.97 archive (`PCB1` + `PCB2 MECR-01` + `PCB3`) |
| [`H03_3BOARD_DRC_AND_ROUTING_REPORT.md`](./H03_3BOARD_DRC_AND_ROUTING_REPORT.md) | Full before/after DRC comparison vs PR #40, `U2` BGA VIPPO, QSPI clustering, and 3-board architecture |
| [`BLOCKED.md`](./BLOCKED.md) | Honest `NOT FOR FAB` manufacturing blockers & closure criteria |
| [`verification-report.json`](./verification-report.json) | Machine-verifiable 3-board verification receipt |
| [`evidence/pre-route/`](./evidence/pre-route/) & [`evidence/post-route/`](./evidence/post-route/) | Raw live EasyEDA Pro V4.1.97 pre/post dumps, strict DRC JSONs, live commit receipt & export receipt |
| [`SHA256SUMS.txt`](./SHA256SUMS.txt) | Cryptographic integrity manifest |

## Reproducible Verification Command

```bash
python3 -B hardware/evt1-native-eda-20261118/h03-bridge-route-3board/verify_h03_3board.py \
  --root hardware/evt1-native-eda-20261118/h03-bridge-route-3board \
  --out /tmp/h03-3board-verify.json
```
