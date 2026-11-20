# EVT-1 H03 PR #41 Data Forensic Audit, Three-Board Routing Progress & Strict ERC/DRC Report

- **Project**: 智元跃动 AI/AR 智能眼镜 V1.0 (`EVT-1`)
- **Engineering Baseline Inherited**: **PR #41** (`hardware/evt1-h03-bridge-route-3board-20261120` @ `a97e2fb`) & **PR #40** (`22.0 × 4.2 mm` Track A untouched)
- **Live EDA Tool**: EasyEDA Pro **V4.1.97** (`easyeda-agent v1.17.0`, live save/reload/DRC/ERC/export)
- **Exported Archive**: `native/ZY_AIAR_EVT1_H03_3BOARD_ROUTED_MECR01_NOT_FOR_FAB.epro2` (`1,231,427 bytes`, SHA256 `62e1f3cd21b36420bf1b5da6d2af57abd6e6ed67f221c55bfc59516aad117571`)
- **Manufacturing Release Status**: **`NOT FOR FAB` / `BLOCKED`** (Zero DRC/ERC rules disabled or relaxed)

---

## 1. Forensic Audit of PR #41 Saved Data (`340` CLI Tracks vs `323` Persisted Lines)

Before adding any new copper, we audited PR #41's archived `.epro2` (`h03-bridge-route-3board/native/ZY_AIAR_EVT1_H03_3BOARD_MECR01_TRIAL_NOT_FOR_FAB.epro2`) against its live CLI commit log, persisted post-route dumps, and live export receipt:

1. **Archive & Reload Consistency (100% Confirmed)**:
   - PR #41 `.epro2` SHA256 (`82a7f78219b7262749d5051241cb5b0fab2ecd67b703b550dc6d84e33a143b62`) matches `h03-bridge-route-3board/evidence/post-route/archive-response.json` byte-for-byte.
   - Internal `.epro2` `LINE`/`VIA` primitive counts match PR #41 `PCB{1,2,3}-post.dump.json` **100%** (`PCB1: 11L/19V`, `PCB2: 300L/28V`, `PCB3: 12L/12V` → Total `323L / 59V`). No data was lost during save, reload, or GitHub archival.
2. **Exact Per-Net Cause of `340 → 323` (`-17` Tracks)**:
   - `PCB1`: `11` CLI track commands → `11` persisted lines (`0` delta).
   - `PCB3`: `12` CLI track commands → `12` persisted lines (`0` delta).
   - `PCB2`: `318` initial CLI track commands − `1` surgically deleted stub (`289e845e09bfd08f` on `VSYS`) = `317` committed tracks → `300` persisted lines (`-17` delta).
   - Per-net geometric diff across all `13` routed nets on `PCB2` proved that **`11/13` nets had `0.0 mil` length delta**; **ONLY two multi-pin nets** experienced collinear overlap deduplication by EasyEDA Pro's native geometry engine during `pcb save + doc reload`:
     - `FPGA_CDONE_VSYNC_N`: **`-7` segments (`-56.9 mil`)** — pairwise MST router allowed same-net branches to re-traverse an identical shared grid corridor.
     - `VSYS`: **`-11` segments (`-105.6 mil`, including `-1` surgically deleted stub `289e845e09bfd08f`)** — same shared-corridor collinear overlap merged on reload.
3. **Engineering Fix Implemented in This Round (PR #42)**:
   - Replaced pairwise MST routing with a **Union-Find Kruskal-Steiner Forest** router (`route_3board_engine.py`) that routes directly into already-laid same-net Steiner copper without duplicating shared corridor segments, plus **2-pass same-layer `GND` pad chaining**.
   - **Verified Result on PR #42 Save/Reload/Export**:
     - `1,175` CLI track commands − `1` surgically deleted track on `PCB2` (`19339d6f995e4f0a`, eliminating `2` `MK2_1`/`MK2_2` clearance errors) = `1,174` net tracks → **`1,233` persisted copper lines** (zero overlap loss; `+59` segments from EasyEDA Pro's native T-junction/via node splitting), and **`135` CLI vias → `135` persisted vias**.
     - **100% Exact Parity**: `post-route/PCB{1,2,3}-post.dump.json` == `.epro2` `LINE`/`VIA` records == `archive-response.json` SHA256 (`62e1f3cd...`).

---

## 2. Three-Board Strict DRC & Real Copper Progress (Before PR #41 vs After PR #42)

All strict DRC runs were executed live in **EasyEDA Pro V4.1.97** (`easyeda pcb drc --strict --json`) under locked 6-layer HDI rules (**zero rules relaxed or suppressed**):

| Board | Outline / Track | Placed Parts / Pads | Copper Lines (`PR #41 → PR #42`) | Vias (`PR #41 → PR #42`) | Clearance / Short / Plane / Mic (`PR #42`) | Unconnected (`Connection` DRC) (`PR #41 → PR #42`) | Real Unconnected Delta | Total Strict DRC (`PR #41 → PR #42`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`PCB1`** (`M-MAIN-L`) | `8.2 × 46.0 mm` stepped (`5.8 mm` stem) | `118 / 507` | `11 → 554` (`+543`) | `19 → 78` (`+59`) | **`0 / 0 / 0 / 0`** | `464 → 362` | **`-102` (`-22.0%`)** | `465 → 363` |
| **`PCB2`** (`M-OPT-BRIDGE`) | `25.0 × 4.6 mm` (`MECR-01` trial) | `86 / 328` | `300 → 378` (`+78`) | `28 → 26` (`-2`, cleaner Steiner) | **`0 / 0 / 0 / 0`** | `270 → 246` | **`-24` (`-8.9%`)** | `271 → 247` |
| **`PCB3`** (`M-AUD-R`) | `5.2 × 34.0 mm` right temple | `53 / 239` | `12 → 301` (`+289`) | `12 → 31` (`+19`) | **`0 / 0 / 0 / 0`** | `190 → 142` | **`-48` (`-25.3%`)** | `191 → 143` |
| **3-Board Total** | **6L HDI (`L2/L5` GND planes)** | **`257 / 1,074`** | **`323 → 1,233` (`+910`, `3.82×`)** | **`59 → 135` (`+76`, `2.29×`)** | **`0 / 0 / 0 / 0`** | **`924 → 750`** | **`-174` (`-18.8%`)** | **`927 → 753`** |

> **Note on Remaining `1` `Netlist Error (Import Changes)` per PCB**: Identical to PR #40/#41 — reflects the `BLOCKED` unplaced off-board/NDA schematic components (`BAT1`, `SPK1`, `J2`, `J3` on `PCB1`; `BAT1`, `SPK1` on `PCB3`) and hierarchical `CBB*` / `MECR-01` provisional bindings (`PCB2`). Zero unintended net mismatches exist (see Section 4 `207/207` Protel2 parity proof).

---

## 3. Routed Critical Net Inventory Across All Three Boards

### 3.1 `PCB2` (`M-OPT-BRIDGE`, `MECR-01` `25.0 × 4.6 mm` Trial) — `378` Lines, `26` Vias (`13` Routed Nets)
- **FPGA `U2` (`iCE40UP5K-UWG30`) BGA Escape, QSPI & 48 MHz Clock**:
  - `clk_48m` (`5` lines, `2` vias — **100% closed**), `opt_l_qdo2_PANEL` (`8` lines — **100% closed**), `opt_l_qdo3_PANEL` (`25` lines — **100% closed**), `opt_r_qdo1_PANEL` (`4` lines — **100% closed**), `opt_r_qdo2_PANEL` (`6` lines, `2` vias — **100% closed**), `SYS_I2C_SCL_1V8` (`53` lines, `2` vias — **100% closed**), `FPGA_CDONE_VSYNC_N` (`37` lines, `5` vias).
- **AVDD Optical Bias & Power / GND Return**:
  - `AVDD_OPT_BIAS` (`17` lines), `AVDD_D3_VSYS` (`10` lines), `VSYS` (`63` lines), `1V8_FPGA_IO` (`19` lines), `1V8_SYS` (`10` lines), `GND` (`121` lines, `15` vias stitching `33/79` GND pads into continuous `L2`/`L5` GND planes with SDF-union `r = 15.2 mil` signal anti-pads and `MK2` `Ø 1.40 mm` acoustic relief).

### 3.2 `PCB1` (`M-MAIN-L`, `8.2 × 46.0 mm` Stepped Left Main Board) — `554` Lines, `78` Vias (`15` Routed Nets)
- **USB, Audio I2S & Camera Privacy Interlock (`ECO-02`/`ECO-07`/`ECO-14`)**:
  - `USB_DP` (`9` lines, `1` via — **100% closed**), `I2S_S3_DOUT_3V3` (`20` lines, `2` vias — **100% closed**), `PRIV_VTH_L` (`24` lines, `2` vias), `VBUS_5V` (`18` lines, `3` vias), `VBUS_5V_USB` (`11` lines, `2` vias).
- **Dual-Battery Isolation, Buck-Boost & Core Power / Thermal Return**:
  - `BK_SW` (`30` lines, `3` vias — **100% closed**), `3V3_SYS` (`117` lines, `7` vias), `VSYS` (`69` lines, `3` vias), `VBAT_R_ISOLATED` (`12` lines), `BB_FB` (`12` lines, `1` via), `1V8_SYS` (`10` lines), `1V8_FPGA_IO` (`3` lines), `BB_L1` (`3` lines), `BB_L2` (`3` lines), `GND` (`213` lines, `54` vias including `U1` ESP32-S3 EPAD `3×3` thermal via array + `87/126` GND pads stitched to `L2`/`L5`, with `24` SDF-union signal anti-pads and `MK1` acoustic relief; `5.8 × 4.2 mm` `ANT1` keepout strictly clear).

### 3.3 `PCB3` (`M-AUD-R`, `5.2 × 34.0 mm` Right Audio & BLE Board) — `301` Lines, `31` Vias (`8` Routed Nets)
- **nRF5340 Clocks (`Y2` 32 MHz HFXO & `Y3` `ECO-08` 32.768 kHz LFXO) & BLE RF Feed**:
  - `BLE_XC1` (`7` lines — **100% closed**), `LFXO_XL2` (`16` lines, `2` vias — **100% closed**), `LFXO_XL1` (`10` lines, `2` vias), `BLE_ANT_FEED` (`10` lines, `2` vias), `BLE_RF_MID` (`31` lines, `1` via).
- **Power & GND Return**:
  - `1V8_SYS` (`66` lines, `1` via), `VBUS_5V` (`6` lines, `1` via), `GND` (`155` lines, `22` vias stitching `51/71` GND pads into `L2`/`L5` GND planes with `9` SDF-union anti-pads and `MK3` acoustic relief; `5.2 × 4.0 mm` `ANT2` keepout strictly clear).

---

## 4. SCH/PCB Netlist Sync & Complete Per-Item Classification of All 27 Strict ERC Items

### 4.1 Live 3-Board Protel2 Netlist Sync (`207 / 207` Exact Match)
Live Protel2 netlists exported from EasyEDA Pro V4.1.97 (`evidence/erc-3board/board-netlists/{M-MAIN-L,M-OPT-BRIDGE,M-AUD-R}.net`) match PR #40 Track A netlists **100% pin-for-pin across all `207` net groups** (`0` missing nets, `0` swapped pins, `0` accidental net edits).

### 4.2 Complete Classification of All 27 Remaining Track A Strict ERC Items (Zero Rules Disabled)
No electrical ERC errors (`error = 0`, `warn = 0`) exist on any of the three boards. All `27` Track A strict ERC flags fall into exactly two non-electrical categories:
- **`18 × ONLYSYMBOL` (Structural EDA Artifact — Non-Blocking)**: EasyEDA Pro hierarchical root-sheet sub-block containers (`CBB*`), which represent schematic sub-sheets rather than physical PCB footprints.
- **`9 × MISSFOOTPRINT` (Genuine Hardware/NDA Blockers — Kept `BLOCKED`)**: Unfrozen NDA optical/camera connectors, mechanical pogo interface, and off-board battery/speaker interconnects.

> **Transparent Note on `MECR-01` Live Trial ERC (`24` vs `27`)**: In the live `MECR-01` (`25.0 × 4.6 mm`) routing project, `M-OPT-BRIDGE` `J2`, `J3`, and `U6` carry provisional mechanical keepout envelopes solely to verify bridge placement/routing corridors, so live `MECR-01` ERC reports `11 + 6 + 7 = 24` (`18 ONLYSYMBOL + 6 MISSFOOTPRINT`). **Track A (`22.0 × 4.2 mm`) remains byte-for-byte untouched and preserves all `27` (`18 ONLYSYMBOL + 9 MISSFOOTPRINT`)**; `J2`, `J3`, and `U6` remain strictly **`BLOCKED`** for manufacturing until signed JBD NDA datasheets arrive.

| # | Board | Rule | Object / RefDes | Primitive / Sheet ID | Category | Disposition & Status |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1–7 | `M-MAIN-L` | `ONLYSYMBOL` | `CBB1`–`CBB7` (`7` items) | `ie24, ie30, ie36, ie42, ie48, ie54, ie60` (`4d38590959875927`) | Hierarchical sheet-block symbols | **Structural EasyEDA artifact** (not physical parts; rules kept enabled) |
| 8 | `M-MAIN-L` | `MISSFOOTPRINT` | `SPK1` | `ie447` (`2ef9ed7773e0c42f`) | Off-board left speaker | **`BLOCKED`** — Awaiting ID/ME spring-contact / solder-pad spec |
| 9 | `M-MAIN-L` | `MISSFOOTPRINT` | `J2` | `ie165` (`89cd87358a17e3c2`) | Camera module FPC connector | **`BLOCKED`** — Camera module NDA pinout & connector P/N unfrozen |
| 10 | `M-MAIN-L` | `MISSFOOTPRINT` | `J3` | `ie284` (`89cd87358a17e3c2`) | Magnetic charging/USB pogo header | **`BLOCKED`** — Mechanical pogo pitch & pinout unfrozen |
| 11 | `M-MAIN-L` | `MISSFOOTPRINT` | `BAT1` | `ie226` (`3fdc6001a068d82e`) | Off-board left LiPo cell | **`BLOCKED`** — Awaiting ID/ME wire-pad / BTB battery interface spec |
| 12–17 | `M-OPT-BRIDGE` | `ONLYSYMBOL` | `CBB1`–`CBB6` (`6` items) | `ie24, ie30, ie36, ie42, ie48, ie54` (`e00fbca5c08cc114`) | Hierarchical sheet-block symbols | **Structural EasyEDA artifact** (not physical parts; rules kept enabled) |
| 18 | `M-OPT-BRIDGE` | `MISSFOOTPRINT` | `U6` | `ie420` (`d643a0611d67a31a`) | Optical AVDD / bias IC | **`BLOCKED`** — JBD NDA AVDD rail spec unfrozen *(provisional envelope in MECR-01 trial only)* |
| 19 | `M-OPT-BRIDGE` | `MISSFOOTPRINT` | `J2` | `ie125` (`b1ec1f299f13f9eb`) | Left JBD013VG light-engine FPC | **`BLOCKED`** — JBD NDA pinout & Hirose P/N unfrozen *(provisional envelope in MECR-01 trial only)* |
| 20 | `M-OPT-BRIDGE` | `MISSFOOTPRINT` | `J3` | `ie188` (`b1ec1f299f13f9eb`) | Right JBD013VG light-engine FPC | **`BLOCKED`** — JBD NDA pinout & Hirose P/N unfrozen *(provisional envelope in MECR-01 trial only)* |
| 21–25 | `M-AUD-R` | `ONLYSYMBOL` | `CBB1`–`CBB5` (`5` items) | `ie24, ie30, ie36, ie42, ie48` (`e98944c2045546cf`) | Hierarchical sheet-block symbols | **Structural EasyEDA artifact** (not physical parts; rules kept enabled) |
| 26 | `M-AUD-R` | `MISSFOOTPRINT` | `SPK1` | `ie377` (`8fa31840ba825b92`) | Off-board right speaker | **`BLOCKED`** — Awaiting ID/ME spring-contact / solder-pad spec |
| 27 | `M-AUD-R` | `MISSFOOTPRINT` | `BAT1` | `ie65` (`bbbca101b360e299`) | Off-board right LiPo cell | **`BLOCKED`** — Awaiting ID/ME wire-pad / BTB battery interface spec |

---

## 5. Structural Baseline Preservation Verification

- **Original `22.0 × 4.2 mm` Bridge Baseline (`Track A`)**: `hardware/evt1-native-eda-20261118/h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2` — **100% untouched** (SHA256 verified identical by `verify_h03_3board_routing_hdi.py`).
- **PR #41 Baseline Archive**: `hardware/evt1-native-eda-20261118/h03-bridge-route-3board/native/ZY_AIAR_EVT1_H03_3BOARD_MECR01_TRIAL_NOT_FOR_FAB.epro2` — **100% untouched** (`82a7f782...`).
- **`MECR-01` (`25.0 × 4.6 mm`) Routing Archive**: `hardware/evt1-native-eda-20261118/h03-3board-routing-hdi/native/ZY_AIAR_EVT1_H03_3BOARD_ROUTED_MECR01_NOT_FOR_FAB.epro2` — independent engineering trial; **NOT approved to replace `22.0 × 4.2 mm` without formal ID/ME sign-off**.
