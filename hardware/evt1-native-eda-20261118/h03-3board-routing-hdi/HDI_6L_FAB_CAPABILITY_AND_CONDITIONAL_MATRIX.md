# EVT-1 6-Layer HDI Fabrication Capability, Impedance & RF Antenna Keepout Audit Matrix

- **Project**: 智元跃动 AI/AR 智能眼镜 V1.0 (`EVT-1`)
- **Stage**: `H03` Three-Board PCB Routing & Manufacturing Rule Audit
- **Manufacturing Release Status**: **`NOT FOR FAB` / `BLOCKED`**
- **Rule Lock Policy**: Zero EasyEDA Pro DRC rules relaxed; every parameter unverified by a signed fab stackup/DFM sheet or VNA bench sweep is explicitly marked **`CONDITIONAL`** or **`BLOCKED`**.

---

## 1. Executive Summary

| Audit Domain | EVT-1 Design Requirement / Current EDA Parameter | JLCPCB 6L HDI Published Capability | PCBWay 6L HDI / Advanced HDI Published Capability | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Layer Count & Structure** | 6-Layer `L1–L6` (`L2`/`L5` GND planes, `0.8 mm` nominal target) | 6L HDI `1+N+1` / `2+N+2` supported (`0.4–2.0 mm`) | 6L HDI `1+4+1` / `2+2+2` SBU supported (`0.4–2.4 mm`) | **`PASS` (Structure)** |
| **Min Trace Width / Space (Fine Pitch Escape)** | `2.5 mil / 2.5 mil` (`63.5 µm`) on FPGA `U2` QSPI/clock & dense corridors (EasyEDA Pro locked default rule = `6.0 mil` std / fine escape) | **`3.0–3.5 mil` (`0.076–0.09 mm`)** standard 6L HDI (`0.5 oz` / `1 oz`) — **`2.5 mil` is BELOW standard JLCPCB 6L HDI** | Standard HDI `3.0 mil`; Advanced HDI / mSAP down to **`2.0–2.4 mil` (`50–60 µm`, `≤ 0.5 oz` Cu, fab DFM review)** | **`CONDITIONAL`** (Must either confirm `2.5 mil` advanced HDI tier with fab OR widen to `≥ 3.0 mil` where geometry allows) |
| **Microvia Drill / Pad (`4 / 8 mil`)** | `4.0 mil` (`0.10 mm`) drill / `8.0 mil` (`0.20 mm`) pad (`0.05 mm` annular ring) | Laser blind microvia **`0.075–0.15 mm` (`0.10 mm` std)**, pad `≥ 0.20–0.25 mm`, aspect ratio **`≤ 1:1`** (typical `≤ 0.8:1`); mechanical through-drill min **`0.15 mm` (`6 mil`)** | Laser blind microvia **`0.10 mm` (`4 mil`)**, pad `≥ 0.20–0.25 mm`, aspect ratio `≤ 1:1`; mechanical through-drill min **`0.15 mm` (`6 mil`)** | **`CONDITIONAL`** (`4/8 mil` is ONLY manufacturable as **laser blind microvia `L1–L2` / `L5–L6`**, NOT `0.8 mm` through-via; EasyEDA CLI currently places through-vias and requires blind-via span conversion before Gerber/ODB++ release) |
| **Via-in-Pad (VIPPO / POFV)** | `U2` iCE40UP5K `UWG30` (`0.35 mm` pitch) & `U11` nRF5340 `WLCSP95` (`0.35 mm` pitch) + `U1` ESP32-S3 EPAD thermal array | POFV (Epoxy filled & copper-capped) standard on 6L+ HDI; **free/standard on 6L+ with `≥ 0.15 mm` mech or laser microvia** | Standard HDI VIPPO for `0.40 mm` BGA; **Advanced HDI VIPPO** for `0.35 mm` WLCSP | **`CONDITIONAL`** (Requires fab-confirmed `0.35 mm` WLCSP laser VIPPO DFM sign-off & `NSMD` land tolerance check) |
| **WLCSP `0.35 mm` Ball-to-Ball Copper Clearance** | `U2` (`0.18 mm` NSMD) & `U11` (`0.195 mm` NSMD → `6.103 mil` gap) vs `6.0 mil` locked DRC | Supported with laser microvia + solder-mask dam review (NSMD preferred over SMD for `0.35 mm` pitch) | Supported under Advanced HDI `0.35 mm` WLCSP rules | **`CONDITIONAL`** (Zero EasyEDA DRC violations achieved, but requires fab solder-mask bridge capability check `≥ 0.075–0.10 mm`) |
| **Controlled Impedance (`50 Ω` SE / `90 Ω` Diff)** | `50 Ω` RF GCPW (`ANT1`/`ANT2`), `50 Ω` QSPI/48 MHz clock, `90 Ω` USB FS `D+/D-` | Standard **`±10%`** TDR controlled impedance (`≥ 50 Ω` SE, `90/100 Ω` diff) using published 6L stackups (`JLC06161H-3313` etc.) | Standard **`±10%`** (`±8%` / `±5%` optional) TDR impedance with custom 6L HDI prepreg stackup | **`CONDITIONAL`** (Actual trace width/gap must be locked to selected fab's dielectric `Dk` and prepreg thickness `H1`/`H2` after fab stackup sign-off) |
| **RF Antenna Keepout (`ANT1` & `ANT2`)** | Johanson `2450AT18B100E`: `PCB1 ANT1` = **`5.8 × 4.2 mm`**, `PCB3 ANT2` = **`5.2 × 4.0 mm`** (all 6 layers clear of copper) | N/A (antenna vendor spec) | N/A (antenna vendor spec) | **`CONDITIONAL`** (Johanson datasheet reference clearance is **`6.5 × 6.5 mm`**; EVT-1 slim temple keepouts are compact sub-reference and require real-enclosure VNA `S11` & π-match tuning) |
| **Acoustic Port (`MK1`, `MK2`, `MK3`)** | Infineon `IM69D130V01` bottom-port `Ø 0.8–1.0 mm` NPTH + `Ø 1.40 mm` (`r = 28 mil`) L2/L5 anti-pad | Standard NPTH drill tolerance `±0.05–0.08 mm`, copper-to-NPTH clearance `≥ 0.25–0.30 mm` | Standard NPTH drill tolerance `±0.05 mm`, copper-to-NPTH `≥ 0.25 mm` | **`PASS` (DRC Clean)** (`0` acoustic clearance violations across all 3 boards; gasket seal stays mechanical EVT check) |
| **Unfrozen Optical / Camera / Mechanical Interfaces** | `PCB2 J2/J3/U6` (JBD NDA), `PCB1 J2` (Camera NDA), `PCB1 J3` (Pogo), `BAT1`/`SPK1` (off-board) | N/A — Missing vendor datasheets / pinouts | N/A — Missing vendor datasheets / pinouts | **`BLOCKED`** (No vendor pinout guessing; fabrication strictly prohibited) |

---

## 2. Detailed Fabrication Evidence & Engineering Constraints

### 2.1 6-Layer HDI Trace/Space & Microvia Aspect Ratio (`CONDITIONAL`)

1. **Published Fab Capabilities Checked**:
   - **JLCPCB 6L HDI** (`https://jlcpcb.com/capabilities/pcb-capabilities`):
     - Minimum trace width / spacing on standard 6-layer HDI (`0.5 oz` outer / `0.5 oz` inner): **`3.0–3.5 mil` (`0.076–0.09 mm`)**.
     - Laser blind microvia drill: **`0.075–0.15 mm`** (`0.10 mm / 4 mil` nominal), aspect ratio **`≤ 1:1`** (recommended `≤ 0.8:1` across `~65–100 µm` dielectric between `L1–L2` and `L5–L6`).
     - Minimum mechanical through-hole drill: **`0.15 mm` (`6 mil`)** with `≥ 0.25–0.30 mm` finished pad (cannot drill `0.10 mm` through a `0.80 mm` stackup because aspect ratio would be `8:1`, violating mechanical drilling physics).
     - POFV (Via-in-Pad Plated Over, epoxy-filled & copper-capped) available on 6-layer+ HDI.
   - **PCBWay Advanced 6L HDI** (`https://www.pcbway.com/capabilities.html`):
     - `1+4+1` (1-step HDI) and `2+2+2` (2-step HDI) SBU stackups.
     - Standard HDI: `3.0 mil` (`0.076 mm`) trace/space, `0.10 mm` laser blind microvia, `0.40 mm` BGA VIPPO.
     - Advanced HDI / fine-line tier: **`2.0–2.4 mil` (`50–60 µm`)** trace/space on `≤ 0.5 oz` copper and **`0.35 mm` WLCSP** laser VIPPO (subject to per-job fab DFM review).
2. **Action Required Before EVT-1 Tape-Out**:
   - Convert all `4/8 mil` (`0.10/0.20 mm`) `L1–L2` / `L5–L6` microvias in EasyEDA Pro from through-hole spans (`L1–L6`) to **true laser blind microvia drill pairs (`L1–L2`, `L5–L6`)**, and retain mechanical buried/through vias at **`≥ 0.15 mm / 0.30 mm` (`6/12 mil`)**.
   - Lock the exact `0.8 mm` 6-layer `1+4+1` (or `2+2+2`) stackup with the selected Tier-1/PCBWay/JLCPCB vendor, confirming whether `2.5 mil` (`63.5 µm`) corridors are accepted in their `≤ 0.5 oz` HDI process or whether those few fine-escape tracks must be widened to `3.0 mil` (`76 µm`).

### 2.2 Controlled Impedance Targets (`CONDITIONAL`)

| Net Class | Target Impedance | Board(s) | Current Routed Geometry | Fab Sign-Off Dependency |
| :--- | :--- | :--- | :--- | :--- |
| **2.4 GHz BLE / Wi-Fi RF Feed** (`ANT1`, `ANT2`, `BLE_RF_MID`, `BLE_ANT_FEED`) | `50 Ω ± 10%` Single-Ended GCPW (ref `L2` GND) | `PCB1`, `PCB3` | Short coplanar feed (`8.0 mil` / `5.0 mil` placeholder) | Must recompute exact trace width & coplanar gap from signed fab `L1–L2` prepreg height (`~65–80 µm`, `Er ≈ 3.8–4.2`) |
| **USB 2.0 FS Differential Pair** (`USB_DP`, `USB_DM`) | `90 Ω ± 10%` Differential (`L1` ref `L2` GND) | `PCB1` | `USB_DP` routed (`4.0 mil`); `USB_DM` coupled pairing pending final stackup | Requires fab-verified diff width/spacing + length match (`ΔL < 2 mm` for 12 Mbps FS) |
| **QSPI Optical Data & 48 MHz Clock** (`clk_48m`, `opt_l_qdo*`, `opt_r_qdo*`) | `50 Ω ± 10%` Single-Ended (`L1`/`L6` ref `L2`/`L5` GND) | `PCB2` | `2.5–3.0 mil` routed over continuous `L2`/`L5` GND planes | Lock final width to fab `L1–L2` / `L5–L6` dielectric thickness; verify QSPI trace skew `< 50 ps` (`~7 mm`) |
| **Audio I2S / PDM Clocks** (`I2S_S3_DOUT_3V3`, `PDM_CLK`) | `50 Ω` nominal / series damped | `PCB1`, `PCB2`, `PCB3` | Routed over `L2`/`L5` GND reference | Low-speed (`≤ 3.072 MHz`); series termination (`22–33 Ω`) verified at H04 bring-up |

### 2.3 Johanson `2450AT18B100E` 2.4 GHz Chip Antenna Keepout Audit (`CONDITIONAL`)

- **Official Datasheet Baseline** (`Johanson Technology 2450AT18B100E`, 2450 MHz ceramic chip antenna, `3.2 × 1.6 × 1.3 mm`):
  - Recommended ground-plane clearance (all layers clear of copper beneath & around antenna): **`6.5 × 6.5 mm`**.
  - Requires `50 Ω` feed line + shunt/series π-matching network immediately adjacent to the antenna feed pad, tuned inside the **final plastic/metal-accent eyeglass temple housing** (human head/temple dielectric loading shifts resonant frequency downward by `50–150 MHz`).
- **EVT-1 Actual All-Layer Keepouts Implemented in EDA**:
  - **`PCB1` (`M-MAIN-L`, Wi-Fi/BLE ESP32-S3)**: `X ∈ [0, 5.80] mm`, `Y ∈ [0, 4.20] mm` (**`5.8 × 4.2 mm`** all-layer copper keepout; `L2/L5` GND plane strictly trimmed above `Y ≥ 176.0 mil = 4.47 mm`).
  - **`PCB3` (`M-AUD-R`, BLE Audio nRF5340)**: `X ∈ [0, 5.20] mm`, `Y ∈ [0, 4.00] mm` (**`5.2 × 4.0 mm`** all-layer copper keepout; `L2/L5` GND plane strictly trimmed above `Y ≥ 168.0 mil = 4.27 mm`).
- **Engineering Verdict**: **`CONDITIONAL`** — Both keepouts are physically bounded by the `40 g` slim eyeglass temple widths (`5.8 mm` and `5.2 mm`) and are **smaller than Johanson's `6.5 × 6.5 mm` reference area**. Therefore:
  1. Antenna radiation efficiency and return loss (`S11 < -10 dB` across `2400–2483.5 MHz`) **cannot be claimed as PASS** from geometry alone.
  2. EVT-1 bring-up (`H04`) MUST reserve the π-matching network (`C/L` 0201 footprints already placed adjacent to `ANT1`/`ANT2`) and execute real-enclosure VNA `S11` tuning + OTA TRP/TIS measurement on a phantom head fixture.

---

## 3. Structural & Manufacturing Gate Summary

- **Track A Baseline (`22.0 × 4.2 mm`)**: Preserved byte-for-byte untouched in `h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2`.
- **Track B Trial (`25.0 × 4.6 mm`, `MECR-01`)**: Strictly an independent engineering routing trial; **cannot replace `22.0 × 4.2 mm` as official baseline without written ID/ME sign-off** (checking nose-bridge clearance, waveguide prism mount, and `40 g` mass budget).
- **Overall Fab Gate**: **`NOT FOR FAB` / `BLOCKED`** until:
  1. All 9 `MISSFOOTPRINT` NDA/mechanical interfaces (`J2/J3/U6` JBD optical, `J2` camera, `J3` pogo, `BAT1`/`SPK1`) are frozen with signed vendor datasheets;
  2. Remaining unrouted airwires across `PCB1`, `PCB2`, `PCB3` are closed to `0` under locked rules;
  3. All `CONDITIONAL` items above (`2.5 mil` HDI tier, laser blind microvia `L1–L2`/`L5–L6` span conversion, signed fab impedance stackup, VNA antenna tuning plan, and `MECR-01` ID/ME approval) are signed off.
