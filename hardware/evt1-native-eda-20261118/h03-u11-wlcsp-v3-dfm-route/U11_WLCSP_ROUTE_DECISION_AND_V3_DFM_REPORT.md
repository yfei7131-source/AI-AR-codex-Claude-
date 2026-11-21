# EVT-1 H03 — PCB3 `U11` (`nRF5340-CMAA-R7`) WLCSP Technical Route Decision, V3 Extended Blind-Via DFM Audit & Priority-Net Incremental Routing Report (PR #46)

- **Inherited Baseline**: PR #45 (`hardware/evt1-h03-hdi-laser-wlcsp-route-20261121` @ `a02f7ba`, CI Run `44864804334` ALL-GREEN)
- **Active Branch**: `hardware/evt1-h03-u11-wlcsp-v3-dfm-route-20261121`
- **EDA Tooling**: Live EasyEDA Pro `V4.1.97` (`easyeda-agent v1.17.0`), sole execution agent Gemini
- **Deliverable Archive**: `native/ZY_AIAR_EVT1_H03_3BOARD_U11_V3_DFM_MECR01_NOT_FOR_FAB.epro2` (`1,245,571` bytes, SHA-256 `4f97612de44ef7e09f781ea07e7e9da7e4de1c40732c874849396c007f8da965`)
- **Release Verdict**: **`NOT FOR FAB` / `BLOCKED`** (all fab/supplier/NDA/ME-unapproved items remain explicitly `BLOCKED` in `BLOCKED.md`; zero DRC rule relaxation)

---

## 1. Priority 1 — `PCB3 U11` (`nRF5340-CMAA-R7`) WLCSP-95 Manufacturing Bottleneck & Formal Technical Route Decision

### 1.1 Real BOM, Nordic Package Lineup & Measured 95-Ball Net Usage
Direct verification against `Inputs/effective_bom.csv` (`BOM-36`), Nordic Semiconductor official `nRF5340` package specifications, and live `PCB3` `.epro2` / `PCB3-post.dump.json` copper coordinates confirms:

- **BOM Part (`BOM-36`)**: **`nRF5340-CMAA-R7`** (Nordic Semiconductor, **WLCSP-95, `3.994 × 4.390 × 0.449 mm`**, measured pitch `13.780 × 13.782 mil = 0.3500 mm`, Nordic CMAA Reference Configuration #3 — DCDC normal voltage, no USB).
  - Note: `nRF5340-CLAA` (`4.390 × 3.994 × 0.404 mm`) is **NRND** (*Not Recommended for New Designs*); `nRF5340-CMAA` is Nordic's active drop-in 95-ball successor.
  - Alternative package: `nRF5340-QKAA` (**aQFN-94, `7.0 × 7.0 × 0.85 mm`**, `0.40 mm` dual-row pitch).
- **Exact `PCB3 U11` 95-Ball Ring Breakdown (Directly Parsed by `independent_hdi_dfm_auditor_v3.py`)**:
  - Ball array footprint spans `X = 33.5..171.3 mil` (`3.500 mm` ball span; `4.15 mm` package body inside `PCB3`'s **`5.20 mm`** temple board width → only `0.525 mm/side` margin).
  - **`43` balls (`45.3%`)**: `NC` / unassigned.
  - **`16` balls (`depth = 0`, Outer Perimeter)**: `A1 BLE_XC1`, `A2 BLE_XC2`, `A3 1V8_SYS`, `A5 GND`, `A7 NRF_DECD`, `A9 NRF_DCCD`, `B1 NRF_DECR_RF`, `B12 1V8_SYS`, `D1 BLE_RF_ANT`, `D12 GND`, `F1 BLE_SWDIO`, `F12 LFXO_XL2`, `K1 1V8_SYS`, `L11 1V8_SYS`, `L3 IPC_S3_TX_1V8`, `L5 1V8_SYS` — **100% escapable on `L1`**.
  - **`22` balls (`depth = 1`, Ring-1)**:
    - `11` Power/GND: `1V8_SYS` (`B7, B10, D2, E11, H11`), `GND` (`B2, B9, B11, C2, K6, K11`).
    - `11` Non-remappable RF/Analog/Clock/SWD/IPC/I2S: `B4:NRF_DECR_RF`, `B5:NRF_DECN`, `B6:NRF_DCC`, `B8:NRF_DECA`, `F2:BLE_SWDCLK`, `F11:LFXO_XL1`, `G2:BLE_NRESET`, `K2:AMP_SD_REQ_1V8`, `K3:IPC_NRF_TX_1V8`, `K4:I2S_LRCLK_1V8`, `K5:I2S_BCLK_1V8`.
  - **`14` balls (`depth ≥ 2`, Deep-Inner)**:
    - `12` `GND` (`E5..E8, F5..F8, G5..G8`).
    - **`2` Signals**: `J4:I2S_AMP_DIN_1V8`, `J5:I2S_S3_DOUT_1V8` (digitally remappable via `PSEL` in a future Rev E2 ECO, **but** Ring-1 still contains `22` fixed analog/RF/SWD/crystal/power balls that cannot be remapped).
  - **Total Inner Balls Blocked Under 1-Stage `0.10/0.25 mm` HDI + Locked `6.0 mil` Rules**: **`36` balls** (`22` Ring-1 + `14` Deep-Inner).

### 1.2 Quantitative 3-Option Engineering Comparison & Formal Decision

| Option | Package & Board Envelope | Process / Design Rules | Geometric & Manufacturing Proof | Mass / ID / Architecture Impact | Formal Verdict |
|---|---|---|---|---|---|
| **Option 1 (Selected): Retain `nRF5340-CMAA-R7` + Upgrade `PCB3` to Tier-1 Advanced HDI (`2+N+2` / IPC-2226 Type III)** | `3.994 × 4.390 × 0.449 mm` inside existing `5.20 × 34.0 mm` `PCB3` (`0.525 mm/side` margin) | `0.075/0.19–0.20 mm` (`3.0/7.5–7.9 mil`) copper-filled stacked/staggered laser VIPPO, `2.0–3.0 mil` L/S (`0.05–0.075 mm`), `0.5 oz` outer copper | Fits `13.78 mil` (`0.35 mm`) pitch cleanly (`7.7 mil` NSMD pad + `3.0/7.5 mil` VIPPO leaves `6.08 mil` pad-to-pad clearance; Nordic official WLCSP-95 reference fanout uses `0.075/0.175–0.20 mm` VIPPO on `2+N+2` HDI) | Preserves `40 g` slim temple ID, binocular AR architecture, BLE 5.4 LE Audio dual-core SoC, and exact Nordic CMAA Config #3 RF topology | **SELECTED FORMAL EVT-1 ROUTE** *(remains `BLOCKED` pending Tier-1 HDI fab EQ — `BLK-FAB-03`)* |
| **Option 2 (Rejected for Wearable): Substitute `nRF5340-QKAA` (`aQFN-94`)** | `7.0 × 7.0 × 0.85 mm` (`+1.80 mm` wider than `PCB3`'s entire `5.20 mm` width; requires `≥ 8.2 mm` board width, `+58%` wider & `+0.40 mm` thicker) | Standard 6L `1+4+1` HDI (`0.10/0.25 mm` blind vias, `3.0–3.5 mil` L/S) | Electrically routable on standard HDI, **but physically impossible** inside the `5.20 mm` right temple PCB envelope | Breaks slim temple ID, hinge clearance, ear-hook ergonomics, and `40 g` mass budget; requires full ME/ID temple redesign | **REJECTED FOR WEARABLE EVT-1** *(documented strictly as non-wearable bench bring-up carrier fallback only)* |
| **Option 3 (Rejected — Unroutable): Retain `5.2 × 34.0 mm` Structure + Standard 1-Stage `0.10/0.25 mm` HDI (`6.0 mil` Locked Rule)** | Existing `5.20 × 34.0 mm` `PCB3` + `nRF5340-CMAA-R7` | Standard 1-stage `1+4+1` `4.0/10.0 mil` dog-bone or `3.0/9.0 mil` VIPPO, `6.0 mil` locked clearance | **Mathematically unroutable**: `13.78 mil` pitch (`7.7 mil` pad) gives `6.08 mil` orthogonal gap and `11.79 mil` diagonal gap; `4.0/10.0 mil` dog-bone leaves `0.89 mil` (`< 6.0 mil`), and `3.0/9.0 mil` VIPPO leaves `5.39 mil` (`< 6.0 mil`) to adjacent balls, stranding `36` active Ring-1 + Deep-Inner balls | Violates electrical completeness without illegally relaxing DRC rules | **REJECTED (MATHEMATICALLY UNROUTABLE)** |

---

## 2. Priority 2 — Extended V3 Manufacturing Audit of All Laser Blind Microvias (`139 → 141`)

`independent_hdi_dfm_auditor_v3.py` (covered by `test_independent_hdi_dfm_auditor_v3.py`, `4/4` passing) audits **every** laser blind microvia across `PCB1`, `PCB2`, and `PCB3` against the board's true EasyEDA Pro outline polygon (including `PCB1`'s stepped notch) and 3D vertical layer spans (`BV_L1_L2 = {1, 15}`, `BV_L5_L6 = {18, 2}`, `NORMAL = {1, 15, 16, 17, 18, 2}`):

| Board | Blind Vias (`PR #45 → PR #46`) | Span Breakdown (`BV_L1_L2` / `BV_L5_L6`) | Min Ring (`≥ 2.95 mil`) | Min Hole (`≥ 2.95 mil`) | Min Cu-to-Edge (`≥ 11.811 mil` / `0.300 mm`) | Min Same-Span Via-Via Cu (`≥ 6.0 mil`) | Min Same-Span Hole Wall (`≥ 8.0 mil`) | Total V3 Violations |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| **PCB1 (`M-MAIN-L`)** | `62 → 62` | `21` / `41` | `3.000 mil` (`0.0762 mm`) | `4.000 mil` | `12.500 mil` (`0.3175 mm`) | `7.702 mil` (`0.1956 mm`) | `13.702 mil` (`0.3480 mm`) | **`0`** |
| **PCB2 (`M-OPT-BRIDGE`)** | `39 → 40` (`+1`) | `27` / `13` | `3.000 mil` (`0.0762 mm`) | `3.000 mil` (`U2` VIPPO `2`) | `14.872 mil` (`0.3777 mm`) | `7.984 mil` (`0.2028 mm`) | `13.984 mil` (`0.3552 mm`) | **`0`** |
| **PCB3 (`M-AUD-R`)** | `38 → 39` (`+1`) | `20` / `19` | `3.000 mil` (`0.0762 mm`) | `4.000 mil` | `13.514 mil` (`0.3433 mm`) | `7.681 mil` (`0.1951 mm`) | `13.681 mil` (`0.3475 mm`) | **`0`** |
| **Total (3 Boards)** | **`139 → 141` (`+2`)** | **`68` / `73`** | **`≥ 3.000 mil`** | **`≥ 3.000 mil`** | **`≥ 12.500 mil`** | **`≥ 7.681 mil`** | **`≥ 13.681 mil`** | **`0`** |

- **3D Untruncated Conflict Matrix (`independent-dfm-v3-summary.json`)**: `TRUE_PHYSICAL_VIOLATION = 0`, `REAL_DFM_VIA_TOUCHES_SMD_PAD = 0`, `RULE_DIFF_HDI_3_TO_6MIL_TRACK_TRACK = 0`, `illegal_mech_through_violations = 0` across all 3 boards.
- **Unapproved Fab Governance**: All items lacking written fab EQ (`6L 0.80 mm` dielectric stackup, `11` VIPPO sites, `PCB3 U11` `2+N+2` Advanced HDI EQ, `ANT1`/`ANT2` keepouts, JBD optical NDA, `MECR-01` structural sign-off) remain **`BLOCKED`**.

---

## 3. Priority 3 & 4 — Live EasyEDA Pro `V4.1.97` Routing Convergence, Strict DRC/ERC & Independent Re-Import Proof

Building incrementally on top of PR #45's verified zero-clearance copper (`incremental_route_on_pr45.py` + `apply_pr46_incremental_and_reimport.py`) with strict `ANT1`/`ANT2` 2.4 GHz RF keepouts (`PCB1 y ≥ 178.0 mil`, `PCB3 y ≥ 170.5 mil`) and ZERO rule relaxation or net deletion:

| Metric (Live EasyEDA Pro `V4.1.97` Strict DRC & `pcb check`) | PCB1 (`PR #45 → PR #46`) | PCB2 (`PR #45 → PR #46`) | PCB3 (`PR #45 → PR #46`) | 3-Board Total (`PR #45 → PR #46`) |
|---|---:|---:|---:|---:|
| **Persisted Copper Tracks (`≥ 3.0 mil`)** | `804 → 808` (`+4`) | `384 → 394` (`+10`) | `375 → 380` (`+5`) | **`1,563 → 1,582` (`+19`)** |
| **Persisted Vias (`Blind` / `Mech 6/12` / `Thermal 8/14`)** | `98 → 98` (`62/27/9`) | `46 → 47` (`40/7/0`, `+1` blind) | `50 → 51` (`39/12/0`, `+1` blind) | **`194 → 196` (`141/46/9`, `+2` blind)** |
| **Strict DRC Clearance / Short / Plane / Mic Errors** | `0 → 0` | `0 → 0` | `0 → 0` | **`0 → 0`** |
| **Strict DRC Total Unconnected (`Connection Error`)** | **`359 → 358` (`-1`)** | **`242 → 238` (`-4`)** | **`138 → 136` (`-2`)** | **`739 → 732` (`-7`)** |
| **Strict DRC Non-GND Unconnected** | `307 → 307` (`0`) | **`206 → 204` (`-2`, `OPT_SCK_R` 100%)** | `114 → 114` (`0`) | **`627 → 625` (`-2`)** |
| **Strict DRC GND Unconnected** | **`52 → 51` (`-1`)** | **`36 → 34` (`-2`)** | **`24 → 22` (`-2`)** | **`112 → 107` (`-5`)** |
| **`pcb check` Dangling / Dup / Float / OverPad / Coupling** | `0 / 0 / 0 / 0 / 0` | `0 / 0 / 0 / 0 / 0` | `0 / 0 / 0 / 0 / 0` | **`0 / 0 / 0 / 0 / 0`** |
| **`pcb check` `decapTooFar`** | `3 → 3` | `10 → 10` | `0 → 0` | **`13 → 13`** |
| **Independent Fresh Re-Import Parity (`DRC` / `Copper` / `Blind Rules`)** | **100% Exact Match** | **100% Exact Match** | **100% Exact Match** | **`drc_exact_match=True`** |

### Why Additional Non-GND Unconnected Nets Remain Blocked Under Locked `6.0 mil` Rules
Under locked `6.0 mil` clearance (`3.0 mil` min trace, `12.0 mil` mechanical through-via pad + `35.6 mil` `L2/L5` anti-pad diameter) and 1-stage `1+4+1` HDI, the remaining `625` non-GND and `107` GND unconnected pads are physically bounded by:
1. `PCB3 U11` (`0.35 mm` WLCSP-95): `36` Ring-1 + Deep-Inner balls physically unroutable until `BLK-FAB-03` (`2+N+2` Tier-1 HDI rules) is approved.
2. `PCB2 U2` (`0.40 mm` FPGA BGA) & `J1`/`J2`/`J3` fine-pitch optical connectors: inner-ring escape requires approved `0.075/0.20 mm` VIPPO + `< 4 mil` HDI clearance rules (`BLK-FAB-01`, `BLK-FAB-02`, `BLK-NDA-01`).
3. `PCB1` `U1`/`U3`/camera/FPC dense arrays & `ANT1`/`ANT2` 2.4 GHz RF keepout floors (`y ≥ 178.0 / 170.5 mil`) preserved intact with zero keepout violation.

---

## 4. Live 3-Board Strict ERC, `207/207` Netlist Parity & Inherited Archive Integrity

- **3-Board Protel2 Netlist Parity vs Track A (`22.0 × 4.2 mm`, PR #40)**: **`207/207` EXACT MATCH** (`M-MAIN-L: 109`, `M-OPT-BRIDGE: 58`, `M-AUD-R: 40`).
- **Live Strict ERC**: **`0` errors, `0` warnings** across all 3 sheets (`24` MECR-01 / `27` Track A `ONLYSYMBOL`/`MISSFOOTPRINT` strictly on unfrozen optical/mechanical/off-board items).
- **Inherited Baselines Untouched (SHA-256 Verified)**: Track A `22.0 × 4.2 mm` (PR #40) and PR #41–#45 archives remain 100% byte-identical.
