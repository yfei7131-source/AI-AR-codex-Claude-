# EVT-1 H03 Three-Board Routing & HDI Audit — Manufacturing & Interface Blockers (`NOT FOR FAB`)

- **Overall Manufacturing Status**: **`BLOCKED` (`NOT FOR FAB`)**
- **Target Architecture Preserved**: True binocular see-through AR, `≤ 40 g` mass target, dual-battery safety isolation, camera privacy hardware interlock (`ECO-02`), FPGA AVDD power-sequencing (`ECO-03`), USB current limiting (`ECO-07`), nRF5340 32.768 kHz LFXO (`ECO-08`), CMOS input tie-off (`ECO-09`), USB ESD GND (`ECO-14`), and **locked 6-layer HDI DRC rules (zero rule relaxation)**.

---

## 1. Hard `BLOCKED` Interfaces (Missing OEM Datasheets / Mechanical Freeze)

No vendor pinout, mating connector part number, or optical rail specification has been guessed or fabricated. All 9 items remain explicitly **`BLOCKED`** (`MISSFOOTPRINT` on Track A `22.0 × 4.2 mm` baseline):

| # | Board | RefDes | Function | Blocker Category | Required Unblock Evidence |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 1 | `M-OPT-BRIDGE` (`PCB2`) | `J2` | Left JBD013VG MicroLED Light-Engine FPC Connector | **NDA Vendor Pinout** | Signed JBD013VG datasheet + mating Hirose FPC connector P/N & mechanical drawing |
| 2 | `M-OPT-BRIDGE` (`PCB2`) | `J3` | Right JBD013VG MicroLED Light-Engine FPC Connector | **NDA Vendor Pinout** | Signed JBD013VG datasheet + mating Hirose FPC connector P/N & mechanical drawing |
| 3 | `M-OPT-BRIDGE` (`PCB2`) | `U6` | Optical Panel AVDD / Bias Power IC | **NDA Optical Rail Spec** | Confirmed JBD013VG AVDD voltage, peak current, sequencing & OEM IC datasheet |
| 4 | `M-MAIN-L` (`PCB1`) | `J2` | Camera Module FPC Connector | **NDA Camera Module** | Frozen camera module P/N, pinout, MIPI/DVP lane map & mating connector datasheet |
| 5 | `M-MAIN-L` (`PCB1`) | `J3` | Magnetic Charging / USB Pogo-Pin Header | **Mechanical Unfrozen** | ID/ME signed pogo-pin pitch, contact count, magnet keepout & pad drawing |
| 6 | `M-MAIN-L` (`PCB1`) | `BAT1` | Left Temple Off-Board LiPo Battery Cell | **Off-Board / ME** | ID/ME decision on wire-solder pad vs BTB connector + NTC routing |
| 7 | `M-MAIN-L` (`PCB1`) | `SPK1` | Left Temple Off-Board Micro-Speaker | **Off-Board / ME** | ID/ME decision on spring-contact pads vs solder pads + acoustic seal |
| 8 | `M-AUD-R` (`PCB3`) | `BAT1` | Right Temple Off-Board LiPo Battery Cell | **Off-Board / ME** | ID/ME decision on wire-solder pad vs BTB connector |
| 9 | `M-AUD-R` (`PCB3`) | `SPK1` | Right Temple Off-Board Micro-Speaker | **Off-Board / ME** | ID/ME decision on spring-contact pads vs solder pads |

> **Note on `MECR-01` (`25.0 × 4.6 mm`) Bridge Trial**: `PCB2` in the independent `MECR-01` trial assigns provisional mechanical keepout envelopes to `J2`, `J3`, and `U6` solely to validate physical placement congestion and routing corridors. Those provisional envelopes **do NOT unblock manufacturing**, and Track A (`22.0 × 4.2 mm`) keeps all 9 items strictly unbound.

---

## 2. Hard `BLOCKED` PCB Closure Items

1. **Unrouted Remaining Airwires (`Connection` DRC > 0)**: Substantial real copper progress has been committed across `PCB1`, `PCB2`, and `PCB3` with `0` clearance violations, but full 100% net closure across all three 6-layer HDI boards (including inner-layer `L3`/`L4` signal routing and high-density BGA/trunk fanout) is still in progress and required before tape-out.
2. **Track A (`22.0 × 4.2 mm`) vs `MECR-01` (`25.0 × 4.6 mm`) Structural Baseline**: `25.0 × 4.6 mm` remains an independent engineering trial (`MECR-01`). It **cannot replace `22.0 × 4.2 mm`** without written ID/ME approval verifying optical waveguide mount, nose-bridge ergonomics, and `≤ 40 g` total mass budget.

---

## 3. `CONDITIONAL` Fabrication & RF Parameters (Pending Vendor / Lab Sign-Off)

Full details in [HDI_6L_FAB_CAPABILITY_AND_CONDITIONAL_MATRIX.md](HDI_6L_FAB_CAPABILITY_AND_CONDITIONAL_MATRIX.md):

1. **`2.5 mil` (`63.5 µm`) Fine-Line Escape**: Below JLCPCB standard 6L HDI (`3.0–3.5 mil`); requires PCBWay / Tier-1 advanced HDI (`≤ 0.5 oz` Cu) DFM sign-off or local trace widening to `≥ 3.0 mil`.
2. **`4/8 mil` (`0.10/0.20 mm`) Microvia Span Conversion**: Manufacturable ONLY as **laser blind microvias (`L1–L2` / `L5–L6`, aspect ratio `≤ 1:1`)**, NOT `0.8 mm` through-vias (mechanical through-drill minimum `0.15 mm / 6 mil`). EasyEDA Pro CLI currently creates through-via primitives; blind-via drill-pair conversion is mandatory prior to Gerber/ODB++ generation.
3. **`0.35 mm` WLCSP VIPPO / Solder-Mask Dam**: Requires fab confirmation on `U2` (`UWG30`) and `U11` (`WLCSP95`) laser POFV & NSMD solder-mask bridge tolerance.
4. **Controlled Impedance (`50 Ω` SE / `90 Ω` Diff)**: Trace widths/gaps must be recomputed against the signed fab 6L HDI prepreg stackup (`Dk`, `H1`/`H2`) with `±10%` TDR coupons.
5. **Compact RF Antenna Keepouts (`ANT1` `5.8 × 4.2 mm`, `ANT2` `5.2 × 4.0 mm`)**: Sub-reference relative to Johanson `2450AT18B100E` `6.5 × 6.5 mm` guideline; requires real-enclosure VNA `S11` & π-network tuning during `H04` bring-up.
