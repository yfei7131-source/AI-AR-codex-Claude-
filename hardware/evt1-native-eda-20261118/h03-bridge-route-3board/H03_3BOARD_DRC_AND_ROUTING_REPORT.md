# EVT-1 H03 3-Board Real PCB Layout, Live Copper Routing & Strict DRC Report

> **Baseline Inherited**: PR #40 (`hardware/evt1-h02-fp-h03-pcb-20261120` @ `c86ea89`).
> **Target EDA**: Live **EasyEDA Pro V4.1.97** (`easyeda-agent v1.17.0`).
> **Structure Baseline Policy**: PR #40's `22.0 × 4.2 mm` Track A archive (`h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2`) is **100% preserved untouched**. The `25.0 × 4.6 mm` (`MECR-01`) bridge remains on this independent engineering trial branch pending formal ID/ME sign-off.
> **Manufacturing Gate**: **`NOT FOR FAB` (BLOCKED)**.

## 1. Live EasyEDA Pro V4.1.97 Strict DRC Scoreboard Across All 3 Boards

| Board | Outline & Stack | Placed / Placeable | Blocked (Unplaced) | Persisted Live Copper | **PR #40 Clearance** | **This Round Clearance** | **Plane Zone Errors** | **Airwires (Pre → Post)** | **Total Strict DRC** |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`PCB1` (`M-MAIN-L`)** | `8.20 × 46.00 mm` stepped (`5.80 mm` stem), 6L HDI | **`118 / 118`** (`507` pads) | `J2` (Cam NDA), `J3` (Pogo TBD), `BAT1`, `SPK1` | **`11` tracks, `19` GND vias** (`9` U1 EPAD + `10` stitch) | *(unlaid)* | **`0`** (`0` MK1, `0` RF KO, `0` edge) | **`1 → 0`** | `468 → 464` (`SMD Pad: 467→459`) | **`465`** |
| **`PCB2` (`M-OPT-BRIDGE`, `MECR-01`)** | `4.60 × 25.00 mm` (`+0.03 g`), 6L HDI | **`86 / 86`** (`328` pads) | *NDA provisional envelopes on `J2/J3/U6`* | **`317` tracks, `28` HDI `4/8 mil` vias** (`15` GND + `13` signal) | `71` | **`0` (`-100%`)** (`0` MK2, `0` L2/L5, `0` edge) | **`2 → 0`** | `308 → 270` (`SMD Pad: 306→262`) | **`338 → 271` (`-67`)** |
| **`PCB3` (`M-AUD-R`)** | `5.20 × 34.00 mm`, 6L HDI | **`53 / 53`** (`239` pads) | `BAT1`, `SPK1` | **`12` tracks, `12` GND vias** | *(unlaid)* | **`0`** (`0` MK3, `0` RF KO, `0` U11 NSMD) | **`2 → 0`** | `196 → 190` (`SMD Pad: 194→186`) | **`191`** |
| **3-Board Total** | **6L HDI locked rules (zero relaxation)** | **`257` real parts (`1,074` pads)** | **`6` external/NDA parts** | **`340` tracks + `59` vias** | — | **`0` across all 3 PCBs** | **`0` across all 3 PCBs** | **`972 → 924` (`-48` airwires)** | — |

## 2. How All `71` PR #40 Bridge Clearance Errors Were Eliminated to `0` (Zero Rule Relaxation)

1. **`64 → 0` `Plane Zone to Via` & `Hole to Plane Zone` Errors**:
   - In PR #40, `16` non-GND signal vias pierced static `L2 (Inner1)` and `L5 (Inner3)` `LAYER_FILL` polygons without anti-pad cutouts (`16 × 2 × 2 = 64` errors).
   - In this round, every non-GND signal via placed on `PCB2` receives an exact **`r = 15.2 mil` (`11.2 mil > 10.0 mil` locked rule)** anti-pad cutout in `L2` & `L5` via signed-distance-field (`SDF`) contour union (`numpy` + `contourpy`), cleanly merging overlapping anti-pads for tightly spaced signal vias while keeping every `GND` via (`>= 21.0 mil` away) solidly bonded to `L2/L5` copper → **`0` Plane Zone clearance errors AND `0` Plane Zone disconnections** after save & reload.
2. **`7 → 0` `MK2` Polygon GND Ring Clearance Errors**:
   - The router now blocks `MK2`'s full BOT body courtyard and non-rectangular polygon GND ring (`e37e14`/`e37e15`), plus `Ø0.80 mm` acoustic slot keepout on both sides → **`0` MK2 errors**.
3. **Functional QSPI Clustering + `U2` BGA Checkerboard VIPPO Fanout (`PCB2`)**:
   - `U2` (`iCE40UP5K-UWG30ITR`, `0.40 mm` pitch) is repositioned on TOP at `(2.30, 9.60) mm` (clear of BOT `J1` ending at `Y=7.25 mm`) with a dedicated BOT BGA VIPPO fanout pocket directly under `U2`'s inner balls.
   - Concentric `4/8 mil` (`0.10/0.20 mm`) HDI VIPPO vias on `U2` inner balls mathematically & live-DRC satisfy EVERY locked rule (`7.615 mil > 6.0 mil` pad-to-via, `9.615 mil > 6.9 mil` hole-to-pad, `18.27 mil > 11.811 mil` diagonal hole-to-hole) — routing **`clk_48m` (`100%`, `5` tracks, `2` vias)** straight out of `U2.B3`!
   - All 14 `0201` QSPI termination resistors (`R13..R26`) are clustered on TOP directly between `J2 ↔ U2 ↔ J3` (left row `rot=270` facing `J2` south, right row `rot=90` facing `J3` north), achieving **`100%` completion on 6 bridge nets** (`clk_48m`, `opt_l_qdo2_PANEL`, `opt_l_qdo3_PANEL`, `opt_r_qdo1_PANEL`, `opt_r_qdo2_PANEL`, `SYS_I2C_SCL_1V8`) plus live copper trunks on `FPGA_CDONE_VSYNC_N`, `OPT_CS_N_L`, `AVDD_PG_NODE`, `1V8_SYS`, `1V8_FPGA_IO`, `VSYS`, and `GND` (15 L2/L5 stitching vias).

## 3. Left Main (`PCB1`) & Right Audio (`PCB3`) Real Physical Layouts

- **`PCB1` (`M-MAIN-L`, `8.20 × 46.00 mm` stepped temple, `118/118` placed, `0` clearance errors)**:
  - `U1` (`ESP32-S3-PICO-1`, `7.48 × 7.48 mm`) seated in the `8.20 × 9.80 mm` stepped head (`0.36 mm > 0.300 mm` edge clearance), with a BOT thermal-via keepout directly behind its `4.0 × 4.0 mm` EPAD and **9 persisted PCB-level `8/14 mil` `GND` thermal vias** (`3×3` array, `1.0 mm` pitch) replacing the 9 netless footprint-embedded vias (`EasyEDA #118`).
  - `ANT1` (`Johanson 2450AT18B100E`) placed at the edge of the locked 6-layer RF keepout (`X=[0,5.80], Y=[0,4.20]`); `L2/L5` `GND` planes trimmed strictly above `Y >= 4.47 mm` (`0` RF keepout violations).
  - `J1` (`Hirose BM28 30+2P`) at the temple hinge; `MK1` (`IM69D130V01`) with BOTH-SIDES acoustic keepout + L2/L5 `Ø1.40 mm` anti-pad (`0` MK1 errors).
  - `J2` (Camera NDA), `J3` (Pogo ID-TBD), `BAT1`, `SPK1` remain unplaced & `BLOCKED`.
- **`PCB3` (`M-AUD-R`, `5.20 × 34.00 mm`, `53/53` placed, `0` clearance errors)**:
  - `U11` (`Nordic nRF5340-CMAA WLCSP95`) placed `rot=90` with Nordic-compliant `0.195 mm` (`7.677 mil`) NSMD lands (`6.103 mil > 6.0 mil` ball-to-ball copper gap, eliminating all `69` same-footprint errors without relaxing global DRC rules).
  - `Y2` (`FA-128` 32 MHz) and `Y3` (`FC-1610AN` ECO-08 32.768 kHz) placed immediately adjacent to `U11`; `ANT2` seated above the locked `Y=[0,4.00]` 6-layer RF keepout with `L2/L5` `GND` planes trimmed above `Y >= 4.27 mm`; `TP6` SWD header along board edge; `MK3` with BOTH-SIDES acoustic keepout + L2/L5 `Ø1.40 mm` anti-pad (`0` MK3 errors).
  - `BAT1`, `SPK1` remain unplaced & `BLOCKED`.

## 4. Honest Status of SCH/PCB Sync (`Import Changes`: `1` per Board)

Each board still displays `1` EasyEDA Pro `Import Changes` (`Netlist Error`) notice in headless CLI DRC because EasyEDA Pro V4.1.97's `pcb import-changes` returns `imported: false, confirm: "no-dialog"` when `pageVisibility == "hidden"` on multi-sheet hierarchical boards (even though `PCB2` has `0` structural/UID/ChannelID/Footprint/pad-net diffs vs live `.enet`, and `PCB1`/`PCB3` intentionally omit the `4` and `2` blocked/off-board parts). This is reported transparently and **NOT** masked.
