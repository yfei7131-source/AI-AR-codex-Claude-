# EVT-1 H03 HDI Manufacturing Constraint Closure, Blind Microvia Verification & Three-Board Routing Report

- **Project**: 智元跃动 AI/AR 智能眼镜 V1.0 (`EVT-1`)
- **Inherited Baseline**: **PR #42** (`hardware/evt1-h03-3board-routing-hdi-20261121` @ `a74ff61`, CI Run `44775173242`) & **PR #40** (`22.0 × 4.2 mm` Track A untouched)
- **Live EDA Software**: EasyEDA Pro **V4.1.97** (`easyeda-agent v1.17.0`, live commit, save/reload, strict DRC/ERC, `drc-rules` readback, official export & **independent fresh re-import round-trip verification**)
- **Exported Archive**: `native/ZY_AIAR_EVT1_H03_3BOARD_HDI_DFM_MECR01_NOT_FOR_FAB.epro2` (`1,228,578 bytes`, SHA256 `57e89c02373d71beb3224c7295b053d1a2a94d5d9d5ed1579dfd1d9ac4cf896d`)
- **Manufacturing Release Gate**: **`NOT FOR FAB` / `BLOCKED`** (Zero DRC/ERC rules disabled or relaxed; unconfirmed fab/RF items explicitly marked `CONDITIONAL` / `BLOCKED`)

---

## 1. Objective 1 — Live EasyEDA Pro V4.1.97 Laser Blind Microvia Layer-Span Verification

### 1.1 Forensic Audit of PR #42 Vias (Why PR #42 Was Non-Manufacturable)
Direct inspection of PR #42's exported `.epcb` records proved that **`126` of `135` vias (`93.3%`)** were stored as `viaType: "NORMAL"` (`L1–L6` full through-hole) with `holeDiameter = 4 mil (0.10 mm)` / `viaDiameter = 8 mil (0.20 mm)`, while `RULE["BLIND","blindVia"]` had an empty `blinds.content = []`:
- Mechanical drilling `0.10 mm` through a `0.80 mm` stackup (`8:1` aspect ratio) violates **both** JLCPCB and PCBWay minimum mechanical drill capability (`0.15 mm / 6 mil`).
- Furthermore, PR #42's inner copper layers had `Inner1(15)=PLANE`, `Inner2(16)=SIGNAL`, `Inner3(17)=PLANE`, `Inner4(18)=SIGNAL` (L2/L4 asymmetric planes instead of symmetric `1+4+1` L2/L5 planes).

### 1.2 Live Proof & Full Conversion in EasyEDA Pro V4.1.97
We verified live in **EasyEDA Pro V4.1.97** that EasyEDA Pro natively supports, DRC-enforces, saves, reloads, exports, and re-imports true **laser blind microvia drill pairs**:
- **`BV_L1_L2`** (`staLayerId: 1 [Top]` ↔ `endLayerId: 15 [Inner1 / L2 GND]`)
- **`BV_L5_L6`** (`staLayerId: 18 [Inner4 / L5 GND]` ↔ `endLayerId: 2 [Bottom]`)

Every single board was upgraded to symmetric **`1+4+1` 6-layer HDI** (`L1 Top / L2 GND(15) / L3 Sig(16) / L4 Sig(17) / L5 GND(18) / L6 Bot`) and **100% of vias** now obey real HDI drill physics:

| Board | `BV_L1_L2` (`4/8 mil` `BLIND` `1↔15`) | `BV_L5_L6` (`4/8 mil` `BLIND` `18↔2`) | `6/12 mil` (`0.15/0.30 mm` `NORMAL` Mech Through) | `8/14 mil` (`0.20/0.35 mm` `NORMAL` Thermal) | Illegal `4/8 mil` `NORMAL` Through-Vias (`PR #42 → PR #43`) | Live `drc-rules` `used=true` & Re-Import Match |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`PCB1`** (`M-MAIN-L`) | `50` | `63` | `18` | `9` (`U1` EPAD) | **`69 → 0`** | **`PASS` (`used: true`)** |
| **`PCB2`** (`M-OPT-BRIDGE`) | `45` (incl. `2` `U2` VIPPO) | `23` | `9` | `0` | **`26 → 0`** | **`PASS` (`used: true`)** |
| **`PCB3`** (`M-AUD-R`) | `28` | `28` | `9` | `0` | **`31 → 0`** | **`PASS` (`used: true`)** |
| **3-Board Total** | **`123`** | **`114`** | **`36`** | **`9`** | **`126 → 0`** | **`100%` Verified** |

> **Electrical Proof of Real Span Enforcement (No Fake Blind Vias)**: During live verification, EasyEDA Pro's native DRC explicitly flagged `BV_L5_L6` vias whenever `L5(18)` `LAYER_FILL` was absent and immediately cleared all `114` `BV_L5_L6` vias + their Bottom-layer `GND` pads the instant `["LAYER_FILL",18]` was populated—proving EasyEDA Pro V4.1.97 genuinely enforces vertical blind-via connectivity rather than treating them as through-vias.

---

## 2. Objective 2 — 6L HDI Fine-Line, BGA/WLCSP, Stackup, VIPPO, Impedance & Antenna Capability Audit

| Parameter | PR #42 Value | PR #43 Actual Verified Value | JLCPCB 6L HDI Spec | PCBWay 6L HDI Spec | Engineering Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Min Trace Width** | `2.5 mil` (`181` tracks `< 3.0 mil`) | **`3.0 mil` (`0.0762 mm`, `0` tracks `< 3.0 mil`)** (`3.0` sig / `3.5–4.0` pwr) | `3.0–3.5 mil` (`0.076–0.09 mm`) std 6L HDI | `3.0 mil` std HDI (`2.0–2.4 mil` adv) | **`PASS` (EDA Width)** / **`CONDITIONAL`** (impedance lock) |
| **Laser Blind Microvia** | `0` (`126` illegal `4/8` through) | **`237` genuine `4/8 mil` (`0.10/0.20 mm`) `BV_L1_L2`/`BV_L5_L6`** | `0.075–0.15 mm` (`0.10 mm` std), pad `≥ 0.20 mm`, AR `≤ 1:1` | `0.10 mm` laser blind, pad `≥ 0.20 mm`, AR `≤ 1:1` | **`CONDITIONAL`** (EDA span resolved; requires fab `75 µm` prepreg confirmation) |
| **Mechanical Through-Via** | `9` (`8/14 mil`) + `126` illegal `4/8` | **`36` × `6/12 mil` (`0.15/0.30 mm`) + `9` × `8/14 mil`** (`0` illegal) | `≥ 0.15 mm` mech drill, `0.30 mm` pad, POFV supported | `≥ 0.15 mm` mech drill, `0.30 mm` pad, VIPPO supported | **`PASS` (Drill Spec)** / **`CONDITIONAL`** (fab POFV sign-off) |
| **6L HDI Physical Stackup (`LAYER_PHYS`)** | Default 2L `1.51 mm` FR4 core | 6 copper layers symmetric `1+4+1` (`L2/L5` GND, `L3/L4` Sig); native `LAYER_PHYS` kept untouched because manual `.epcb` `LAYER_PHYS` edits trigger EasyEDA Pro DRC `INTERNAL_ERROR` | `1+4+1` `0.8 mm` custom/standard 6L HDI | `1+4+1` / `2+2+2` `0.8 mm` SBU HDI | **`CONDITIONAL`** (Target `0.80 mm` `1+4+1` stackup & `Dk` MUST be locked via fab stackup sheet) |
| **FPGA `U2` (`iCE40UP5K-UWG30`)** | Measured in `.epro2`: `WLCSP-30_L2.5-W2.1-R6-C5-P0.40-TL` | **`0.40 mm` pitch**, `7.874 mil` (`0.200 mm`) land, `2` inner `GND` `BV_L1_L2` laser VIPPOs | `0.40 mm` BGA HDI POFV supported | `0.40 mm` BGA standard HDI VIPPO | **`CONDITIONAL`** (Requires fab POFV & solder-mask dam DFM check) |
| **BLE SoC `U11` (`nRF5340-CMAA`)** | Measured in `.epro2`: `Nordic_nRF5340-CMAA_WLCSP95` | **`0.35 mm` pitch**, `7.677 mil` (`0.195 mm`) NSMD land (`6.103 mil` ball-to-ball copper gap `> 6.0 mil`) | Tighter than standard `0.40 mm` tier — requires fab DFM review | Advanced HDI `0.35 mm` WLCSP VIPPO tier | **`BLOCKED / CONDITIONAL`** (Cannot claim fab PASS without signed `0.35 mm` WLCSP fab DFM sign-off) |
| **Controlled Impedance (`50 Ω` SE / `90 Ω` Diff)** | Placeholder widths | `3.0–3.5 mil` over `L2`/`L5` GND planes | `±10%` TDR impedance coupons | `±10%` (`±8%` opt) TDR coupons | **`CONDITIONAL`** (Recompute exact `W/S` after fab `Dk`/`H` lock) |
| **Antenna Keepout (`ANT1`/`ANT2` Johanson `2450AT18B100E`)** | `PCB1: 5.8×4.2 mm`, `PCB3: 5.2×4.0 mm` | Preserved `100%` all-layer clear (`0` copper intrusions) | Reference datasheet clearance = **`6.5 × 6.5 mm`** | Reference datasheet clearance = **`6.5 × 6.5 mm`** | **`CONDITIONAL`** (Sub-reference slim temple clearance; requires H04 real-enclosure VNA `S11` & π-match tuning) |

---

## 3. Objectives 3 & 4 — Three-Board Routing Progress & Strict DRC Comparison (PR #41 → PR #42 → PR #43)

All DRC runs executed live in **EasyEDA Pro V4.1.97** (`pcb drc --strict --json`, zero rules relaxed). Notice that **fewer, cleaner, non-redundant `≥ 3.0 mil` tracks (`971` vs `1,233`) paired with `237` true `BV_L1_L2`/`BV_L5_L6` laser blind microvias eliminated `64` MORE real unconnected records than PR #42** (`238` fewer than PR #41) with **`0` clearance, `0` short, `0` Plane Zone, and `0` acoustic errors** across all three boards:

| Board | Outline / Track | Persisted Lines (`PR #42 → PR #43`) | `< 3.0 mil` Tracks (`PR #42 → PR #43`) | Persisted Vias (`PR #42 → PR #43`) | Illegal `4/8` Through-Vias (`PR #42 → PR #43`) | Clearance / Short / Plane / Mic | Unconnected `Connection` (`PR #41 → PR #42 → PR #43`) | Real Delta vs PR #42 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`PCB1`** (`M-MAIN-L`) | `8.2 × 46.0 mm` stepped | `554 → 436` | `0 → 0` | `78 → 140` (`113` blind + `27` mech) | `69 → 0` | **`0 / 0 / 0 / 0`** | `464 → 362 → 329` | **`-33` (`-9.1%`)** |
| **`PCB2`** (`M-OPT-BRIDGE`) | `25.0 × 4.6 mm` (`MECR-01`) | `378 → 320` | `148 → 0` | `26 → 77` (`68` blind + `9` mech) | `26 → 0` | **`0 / 0 / 0 / 0`** | `270 → 246 → 222` | **`-24` (`-9.8%`)** |
| **`PCB3`** (`M-AUD-R`) | `5.2 × 34.0 mm` right | `301 → 215` | `33 → 0` | `31 → 65` (`56` blind + `9` mech) | `31 → 0` | **`0 / 0 / 0 / 0`** | `190 → 142 → 135` | **`-7` (`-4.9%`)** |
| **3-Board Total** | **Symmetric `1+4+1` 6L HDI** | **`1,233 → 971`** | **`181 → 0`** | **`135 → 282`** | **`126 → 0`** | **`0 / 0 / 0 / 0`** | **`924 → 750 → 686`** | **`-64` (`-8.5%`)** |

### Routed Critical Nets Achieved Under Confirmed `≥ 3.0 mil` + `BV_L1_L2`/`BV_L5_L6` + `6/12 mil` Rules
- **`PCB2` (`M-OPT-BRIDGE`, `MECR-01`)**: `opt_l_qdo2_PANEL` (`100%`), `opt_l_qdo3_PANEL` (`100%`), `opt_r_qdo0_PANEL` (`100%`), `opt_r_qdo1_PANEL` (`100%`), `FPGA_CRESET_B`, `FPGA_CDONE_VSYNC_N`, `OPT_CS_N_L`, `AVDD_QUAL_CLR_N`, `AVDD_D3_VSYS`, `AVDD_PG_NODE`, `1V2_FPGA_CORE`, `1V8_SYS`, `1V8_FPGA_IO`, `VSYS` (`10/34`), and `GND` (**`71/79` = `89.9%` pads grounded** via `45` `BV_L1_L2` + `23` `BV_L5_L6` blind microvias!).
- **`PCB1` (`M-MAIN-L`)**: `USB_DP` (`100%`), `I2S_S3_DOUT_3V3` (`100%`), `BK_SW` (`100%`), `BB_FB` (`100%`), `VBUS_5V_USB`, `VBUS_5V`, `PRIV_VTH_L`, `CAM_DOVDD_1V8` (`4/14`), `CHG_ISO_GATE`, `LS3_VREF2_EN`, `LS4_VREF2_EN`, `VBAT_R_ISOLATED`, `BB_L1/L2`, `VSYS` (`7/14`), `1V8_SYS`, `3V3_SYS` (`11/45`), `1V8_FPGA_IO`, and `GND` (**`117/126` = `92.9%` pads grounded** via `50` `BV_L1_L2` + `63` `BV_L5_L6` + `9` `U1` `8/14` thermal vias!).
- **`PCB3` (`M-AUD-R`)**: `BLE_XC1` (`100%`), `LFXO_XL1`, `LFXO_XL2` (ECO-08), `BLE_ANT_FEED`, `BLE_RF_MID`, `VBUS_5V`, `1V8_SYS` (`8/26`), and `GND` (**`58/71` = `81.7%` pads grounded** via `28` `BV_L1_L2` + `28` `BV_L5_L6` blind microvias!).

---

## 4. Objective 5 — `Import Changes` Diagnosis, Independent Fresh Re-Import Round-Trip & 27-Item ERC Audit

### 4.1 Forensic Diagnosis of `Netlist Error (Import Changes)` (1 per PCB)
- Live execution of `easyeda pcb import-changes --no-sync-designators` on a disposable `PCB2` copy returned `imported: false, confirm: "no-dialog"`, proving that EasyEDA Pro V4.1.97's built-in `Import Changes` dialog refuses to synchronize boards whose linked schematic contains hierarchical KiCad-migrated root-sheet `CBB*` `ONLYSYMBOL` fatal ERC items (`18` total across the 3 schematics—present identically since Codex PR #36).
- In addition, `PCB1` legitimately omits `4` `BLOCKED` missing-footprint components (`BAT1`, `J2`, `J3`, `SPK1`), and `PCB3` legitimately omits `2` `BLOCKED` off-board components (`BAT1`, `SPK1`).
- Direct pin-level verification of all `.epcb` `PAD_NET` records against live exported Protel2 schematic netlists confirms **`207 / 207` net groups 100% matched** (`PCB1: 112`, `PCB2: 58`, `PCB3: 37`) with zero swapped pins or accidental net edits.

### 4.2 Independent Fresh Re-Import Round-Trip Proof
The exported archive `native/ZY_AIAR_EVT1_H03_3BOARD_HDI_DFM_MECR01_NOT_FOR_FAB.epro2` (SHA256 `57e89c02373d71beb3224c7295b053d1a2a94d5d9d5ed1579dfd1d9ac4cf896d`) was **independently re-imported as a brand-new separate project** (`EVT1-H03-REIMPORT-V3-20261121`, UUID `4c3a9f26e9603f8e19add3f932706212930b7e790f2932f97d6f23ba7532f65d`) in EasyEDA Pro V4.1.97:
- **DRC Exact Match (`drc_exact_match = True`)**: `PCB1: 330 (0 clr / 329 conn)`, `PCB2: 223 (0 clr / 222 conn)`, `PCB3: 136 (0 clr / 135 conn)`.
- **Copper Exact Match (`copper_exact_match = True`)**: `PCB1: 436L / 140V`, `PCB2: 320L / 77V`, `PCB3: 215L / 65V` (`971L / 282V` == `.epro2` `LINE`/`VIA` counts 100%).
- **Blind Microvia Rule Exact Match (`blind_rules_exact_match = True`)**: Both `BV_L1_L2` (`1↔15`) and `BV_L5_L6` (`18↔2`) read back `"used": true` on all 3 PCBs.

### 4.3 Complete Classification of All 27 Track A Strict ERC Items (`0` Electrical Errors / `0` Warnings)
- **`18 × ONLYSYMBOL` (Structural Hierarchical Sheet Blocks — Non-Blocking)**: `M-MAIN-L` `CBB1–CBB7` (`7`), `M-OPT-BRIDGE` `CBB1–CBB6` (`6`), `M-AUD-R` `CBB1–CBB5` (`5`).
- **`9 × MISSFOOTPRINT` (Genuine `BLOCKED` Hardware/NDA Interfaces)**: `M-MAIN-L` (`BAT1`, `J2`, `J3`, `SPK1` — `4`), `M-OPT-BRIDGE` (`J2`, `J3`, `U6` — `3`, unbound on untouched Track A `22.0 × 4.2 mm`; provisional mechanical envelopes on independent `MECR-01` trial so live MECR-01 ERC reports `24 = 18 + 6`), `M-AUD-R` (`BAT1`, `SPK1` — `2`).

---

## 5. Structural Baseline Preservation

- **Track A Official Baseline (`22.0 × 4.2 mm`)**: `../h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2` — **100% untouched** (SHA256 verified by CI).
- **Inherited PR #41 & PR #42 Archives**: **100% untouched** (SHA256 verified by CI).
- **Track B `MECR-01` (`25.0 × 4.6 mm`)**: Remains an independent engineering trial; **may not replace `22.0 × 4.2 mm` without formal ID/ME approval**.
