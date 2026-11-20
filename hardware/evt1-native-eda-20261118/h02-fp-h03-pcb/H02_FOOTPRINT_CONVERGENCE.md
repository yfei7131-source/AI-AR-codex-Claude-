# EVT-1 H02 Footprint Convergence & BOM/PCB Attribute Hygiene (PR #39 → Track A)

> **Manufacturing Gate: `NOT FOR FAB` (BLOCKED).** All counts below are measured live from **EasyEDA Pro V4.1.97** strict ERC, Protel2 netlists, and `verify_h02_fp_h03_pcb.py`.

## 1. Strict ERC Convergence Across All 3 Boards

| Board | PR #36 Baseline | PR #38 | PR #39 (Rev E) | **This Round (Track A)** | Cleared This Round | Remaining Breakdown |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `M-MAIN-L` | 124 | 112 | 56 | **11** | **-45** | `7 ONLYSYMBOL` (sheet boxes) + `4 MISSFOOTPRINT` (`BAT1`, `SPK1`, `J2`, `J3`) |
| `M-OPT-BRIDGE` | 84 | 78 | 34 | **9** | **-25** | `6 ONLYSYMBOL` (sheet boxes) + `3 MISSFOOTPRINT` (`J2`, `J3`, `U6`) |
| `M-AUD-R` | 60 | 56 | 40 | **7** | **-33** | `5 ONLYSYMBOL` (sheet boxes) + `2 MISSFOOTPRINT` (`BAT1`, `SPK1`) |
| **TOTAL** | **268** | **246** | **130** | **27** | **-103** | **`18 ONLYSYMBOL` + `9 MISSFOOTPRINT` (`0` electrical errors / `0` warnings)** |

- **112 → 9 `MISSFOOTPRINT` (-92.0%)**: Every single remaining `MISSFOOTPRINT` is an explicitly audited **NDA-blocked** optical/camera device, **ID-TBD** pogo pad array, or **off-board** soldered harness component — **zero guessed pinouts** and **zero fabricated compatibility**.
- **207 Rev E Net Groups 100% Preserved**: Bit-for-bit Protel2 netlist parity with PR #39 across `M-MAIN-L`, `M-OPT-BRIDGE`, and `M-AUD-R` (`verify_h02_fp_h03_pcb.py`: `PASS_EXACT_PR39_PARITY`), including all 5 Rev E safety ECOs (`ECO-03`, `ECO-07`, `ECO-08`, `ECO-09`, `ECO-14`) and `ECO-02` (`LED_3V3_PRIV`).
- **22.0 × 4.2 mm Bridge Baseline Untouched**: Track A strictly preserves `PCB2` at `22.0 × 4.2 mm` (`17` placed components, `0` MK2 errors, `0` clearance errors).

## 2. Newly Created & Bound OEM / IPC Footprints (103 Instances)

| Footprint Asset | OEM / Standard Source | Key Geometry / Pinout | Bound Instances |
| :--- | :--- | :--- | :---: |
| `Nordic_nRF5340-CMAA_WLCSP95` | Nordic nRF5340-CMAA-R7 PS | 95 balls (`A..L` skip `I`, cols `1..12`), `0.35 mm` pitch, `4.39 × 3.994 mm`, `0.21 mm` NSMD | `M-AUD-R: U11` |
| `Hirose_BM28B0.6-30DS_2-0.35V` | Hirose BM28B0.6-30DS/2-0.35V(53) | 30 signal (`0.35 mm` pitch) + `PWR1`/`PWR2`, `7.85 × 1.80 mm` | `M-MAIN-L: J1`, `M-OPT-BRIDGE: J1` |
| `Hirose_BM28B0.6-16DS_2-0.35V` | Hirose BM28B0.6-16DS/2-0.35V(53) | 16 signal (`0.35 mm` pitch) + `PWR1`/`PWR2`, `5.40 × 1.80 mm` | `M-AUD-R: J1` |
| `ROHM_SOD-523_RB521S-30` | ROHM RB521S-30 | SOD-523 (`1.60 × 0.80 mm`), pads `K` / `A` | `M-MAIN-L: D1` |
| `Epson_FA-128_2016_4Pin` | Epson FA-128 32 MHz | `2.0 × 1.6 mm` 4-pad crystal | `M-AUD-R: Y2` |
| `Johanson_2450AT18B100E_1206` | Johanson 2450AT18B100E | `1206` (`3.2 × 1.6 × 1.5 mm`) 2.4 GHz chip antenna (`FEED`) | `M-MAIN-L: ANT1`, `M-AUD-R: ANT2` |
| `IPC_0201_0603Metric` / `0402` / `0603` | IPC-7351B passive standards | SMD 2-pin passive land patterns | 78 passives across 3 boards |
| `EVT1_TP1_0.8mm` / `TP5_SWD` / `TP9_AVDD` | EVT-1 test pad spec | `0.8 mm` 1-pad, `5 × 0.6 mm` SWD array, `9 × 0.6 mm` AVDD array | 16 test points across 3 boards |

## 3. BOM / PCB Attribute Hygiene

| Category | Count | Attribute Setting Applied | Affected Refs |
| :--- | :---: | :--- | :--- |
| Auxiliary Power Flags (`#FLG*`) | **11** | `Add into BOM = no`, `Convert to PCB = no` (excluded from cleaned Rev E.1 BOM CSVs) | `#FLG01..#FLG05` (Bridge), `#FLG01..#FLG04` (Main), `#FLG01..#FLG02` (Audio) |
| DNP RF Shunt Placeholders | **3** | `Add into BOM = no`, `Convert to PCB = yes` (keep copper pads on PCB for RF tuning) | RF π-network DNP shunts |
| Off-Board Harness / Electro-Acoustics | **4** | `Add into BOM = yes`, `Convert to PCB = no` (ordered in BOM, wired off-PCB) | `M-MAIN-L: BAT1, SPK1`; `M-AUD-R: BAT1, SPK1` |
| NDA-Blocked / Provisional DNP | **3** | `Add into BOM = no` until vendor NDA & pinout release | `M-OPT-BRIDGE: J2, J3, U6` |

## 4. Intentionally Retained `BLOCKED` `MISSFOOTPRINT` (9 Items)

| Board | Ref | Function | Blocking Reason |
| :--- | :--- | :--- | :--- |
| `M-MAIN-L` | `J2` | `J_CAM_FPC` Camera Module Connector | Camera module vendor NDA required; pinout & mating receptacle unconfirmed |
| `M-MAIN-L` | `J3` | `J_USB_POGO` Charging / USB Pogo Interface | Mechanical ID pogo pitch, contact count, and temple pad coordinates TBD |
| `M-MAIN-L` | `BAT1` | Left-Temple LiPo Cell | Off-board wire-lead battery (`Convert to PCB = no`; solder pad spacing mechanical-TBD) |
| `M-MAIN-L` | `SPK1` | Left-Temple Micro-Speaker | Off-board acoustic speaker (`Convert to PCB = no`; wire/contact pad mechanical-TBD) |
| `M-OPT-BRIDGE` | `J2` | `J_DISP_L` Left JBD MicroLED FPC | **JBD 0.13" MicroLED NDA BLOCKED** — zero pinout guessing |
| `M-OPT-BRIDGE` | `J3` | `J_DISP_R` Right JBD MicroLED FPC | **JBD 0.13" MicroLED NDA BLOCKED** — zero pinout guessing |
| `M-OPT-BRIDGE` | `U6` | `U6_OPT_AVDD` Optical AVDD Regulator | **JBD AVDD rail voltage, startup sequence & current NDA BLOCKED** |
| `M-AUD-R` | `BAT1` | Right-Temple LiPo Cell | Off-board wire-lead battery (`Convert to PCB = no`) |
| `M-AUD-R` | `SPK1` | Right-Temple Micro-Speaker | Off-board acoustic speaker (`Convert to PCB = no`) |
