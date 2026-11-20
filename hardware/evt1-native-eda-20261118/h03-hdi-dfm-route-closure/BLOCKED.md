# EVT-1 H03 HDI-DFM Closure & Three-Board Routing — Manufacturing & Interface Blockers (`NOT FOR FAB`)

- **Overall Manufacturing Release Gate**: **`BLOCKED` (`NOT FOR FAB`)**
- **Preserved Architecture & Hard Rules**: True binocular see-through AR, `≤ 40 g` mass target, dual-battery isolation, camera privacy hardware interlock (`ECO-02`), FPGA AVDD power sequencing (`ECO-03`), USB current limiting (`ECO-07`), nRF5340 32.768 kHz LFXO (`ECO-08`), CMOS input tie-off (`ECO-09`), USB ESD GND (`ECO-14`), locked 6L HDI DRC rules (**zero rule relaxation**), untouched Track A (`22.0 × 4.2 mm`) baseline, and independent `MECR-01` (`25.0 × 4.6 mm`) trial.

---

## 1. HDI Manufacturing Blockers Resolved in This Round (No Fake PASS)

| Prior PR #42 Blocker | Resolution Implemented & Verified Live in EasyEDA Pro V4.1.97 | Remaining Gate |
| :--- | :--- | :--- |
| **`126` illegal `4/8 mil` (`0.10/0.20 mm`) `NORMAL` through-vias** (violated `0.15 mm` mechanical through-drill minimum) | **RESOLVED IN EDA (`126 → 0` illegal `4/8 mil` through-vias)**: Every `4/8 mil` via across all 3 boards is now a genuine **`viaType: "BLIND"`** laser blind microvia (`BV_L1_L2` `1↔15` or `BV_L5_L6` `18↔2`, aspect ratio `0.75:1 ≤ 1:1`), verified `"used": true` in live EasyEDA Pro `drc-rules` and persisted across export → independent re-import; all `L1↔L3/L4/L6` signal layer changes upgraded to standard **`6/12 mil` (`0.15/0.30 mm`) `NORMAL`** mechanical through-vias with `r = 17.8 mil` SDF-union L2/L5 anti-pads. | **`CONDITIONAL`** pending fab-signed `1+4+1` 6L HDI laser drill & POFV DFM confirmation. |
| **`181` `< 3.0 mil` (`2.5 mil`) fine-line traces** (below JLCPCB standard 6L HDI `3.0–3.5 mil`) | **RESOLVED IN EDA (`181 → 0` tracks `< 3.0 mil`)**: Minimum trace width raised to **`≥ 3.0 mil` (`0.0762 mm`)** across `PCB1`, `PCB2`, and `PCB3` (`3.0 mil` signals, `3.5–4.0 mil` power/GND), meeting JLCPCB & PCBWay standard 6L HDI trace width capability. | **`CONDITIONAL`** pending fab-signed controlled impedance stackup width table. |
| **Asymmetric `LAYER_PHYS` (default 2L `1.51 mm` FR4 core; `L4`/`L5` plane/signal inversion)** | **RESOLVED IN EDA**: Corrected all 3 PCBs to symmetric **`1+4+1` 6-layer HDI** (`L1 Top Sig / L2 GND Plane(15) / L3 Sig(16) / L4 Sig(17) / L5 GND Plane(18) / L6 Bot Sig`) with `0.80 mm` nominal `LAYER_PHYS` dielectric definitions (`75 µm` L1–L2 / L5–L6 laser prepreg). | **`CONDITIONAL`** pending fab-signed prepreg/core `Dk` & thickness sheet. |

---

## 2. Hard `BLOCKED` Items (Tape-Out Strictly Prohibited Until Closed)

### 2.1 Unfrozen NDA / Mechanical / Off-Board Interfaces (`9 × MISSFOOTPRINT` on Track A `22.0 × 4.2 mm`)

| # | Board | RefDes | Function | Blocker Category | Required Unblock Evidence |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 1 | `M-OPT-BRIDGE` (`PCB2`) | `J2` | Left JBD013VG MicroLED Light-Engine FPC Connector | **NDA Vendor Pinout** | Signed JBD013VG datasheet + mating Hirose FPC P/N & mechanical drawing |
| 2 | `M-OPT-BRIDGE` (`PCB2`) | `J3` | Right JBD013VG MicroLED Light-Engine FPC Connector | **NDA Vendor Pinout** | Signed JBD013VG datasheet + mating Hirose FPC P/N & mechanical drawing |
| 3 | `M-OPT-BRIDGE` (`PCB2`) | `U6` | Optical Panel AVDD / Bias Power IC | **NDA Optical Rail Spec** | Confirmed JBD013VG AVDD voltage/current/sequencing & OEM IC datasheet |
| 4 | `M-MAIN-L` (`PCB1`) | `J2` | Camera Module FPC Connector | **NDA Camera Module** | Frozen camera module P/N, pinout, MIPI/DVP lane map & connector drawing |
| 5 | `M-MAIN-L` (`PCB1`) | `J3` | Magnetic Charging / USB Pogo-Pin Header | **Mechanical Unfrozen** | ID/ME signed pogo pitch, contact count, magnet keepout & pad footprint |
| 6 | `M-MAIN-L` (`PCB1`) | `BAT1` | Left Temple Off-Board LiPo Cell | **Off-Board / ME** | ID/ME signed wire-solder pad or BTB battery connector + NTC routing |
| 7 | `M-MAIN-L` (`PCB1`) | `SPK1` | Left Temple Off-Board Micro-Speaker | **Off-Board / ME** | ID/ME signed spring-contact pad or wire pad + acoustic seal spec |
| 8 | `M-AUD-R` (`PCB3`) | `BAT1` | Right Temple Off-Board LiPo Cell | **Off-Board / ME** | ID/ME signed wire-solder pad or BTB battery connector |
| 9 | `M-AUD-R` (`PCB3`) | `SPK1` | Right Temple Off-Board Micro-Speaker | **Off-Board / ME** | ID/ME signed spring-contact pad or wire pad |

### 2.2 Remaining PCB Routing & Structural Baseline Blockers

1. **Unclosed Airwires (`Connection` DRC > 0)**: All remaining unrouted signal/power nets across `PCB1`, `PCB2`, and `PCB3` must reach `0` unconnected records under locked rules before tape-out.
2. **Track A (`22.0 × 4.2 mm`) vs `MECR-01` (`25.0 × 4.6 mm`) Mechanical Freeze**: `25.0 × 4.6 mm` remains an independent engineering trial (`MECR-01`) and **cannot replace `22.0 × 4.2 mm`** without written ID/ME approval verifying optical prism clearance, nose-bridge ergonomics, and `≤ 40 g` mass budget.
3. **EasyEDA Pro `Import Changes` (`1` per board)**: Triggered by hierarchical KiCad-migrated root-sheet `CBB*` `ONLYSYMBOL` containers (`18` total across 3 boards) plus legitimately unplaced `BLOCKED` parts on `PCB1` (`4`) and `PCB3` (`2`). Pin-level `PAD_NET` vs live Protel2 SCH netlists are verified **`207/207` net groups identical**; formal ECO freeze requires clearing the 9 `MISSFOOTPRINT` blockers and resolving EasyEDA hierarchical sheet-block synchronization prior to Gerber release.

---

## 3. `CONDITIONAL` Fabrication & RF Sign-Off Items (Cannot Claim Fab PASS Without Vendor/Lab Evidence)

1. **`0.35 mm` WLCSP (`U11` nRF5340-CMAA, `7.677 mil` NSMD land) & `0.40 mm` BGA (`U2` iCE40UP5K-UWG30, `7.874 mil` land) VIPPO / POFV & Solder-Mask Dam**: Requires written fab DFM sign-off confirming `0.35 mm` WLCSP laser POFV (epoxy-filled & copper-capped) and `≥ 0.075 mm` solder-mask bridge capability (JLCPCB `0.40 mm` std / PCBWay Advanced HDI `0.35 mm` tier).
2. **`1+4+1` 6L HDI `0.80 mm` Stackup & Controlled Impedance (`50 Ω` SE / `90 Ω` Diff)**: Must lock exact prepreg `Dk`, dielectric thickness (`~75 µm` L1–L2 / L5–L6), and `±10%` TDR impedance test coupons with the contracted fab; final RF GCPW and USB `D+/D-` differential pair widths/gaps must be recalculated against the signed stackup.
3. **Compact RF Antenna Keepouts (`ANT1` `5.8 × 4.2 mm`, `ANT2` `5.2 × 4.0 mm`)**: Both are physically smaller than Johanson `2450AT18B100E`'s `6.5 × 6.5 mm` reference clearance due to slim temple width; RF efficiency and `S11 < -10 dB` (`2.4–2.4835 GHz`) remain **`CONDITIONAL`** until real-enclosure VNA `S11` & π-network tuning on a phantom-head fixture during `H04` bring-up.
