# EVT-1 Target 0.80 mm 6-Layer `1+4+1` HDI Physical Stackup Specification & Fab Confirmation Matrix

- **Project**: 智元跃动 AI/AR 智能眼镜 V1.0 (`EVT-1`, `PCB1` / `PCB2` / `PCB3`)
- **Stackup Status**: **`CONDITIONAL`** (Pending written PCB fab stackup & TDR impedance sign-off; **`NOT FOR FAB`**)
- **EasyEDA Pro V4.1.97 Official CLI Verification Result**:
  - Executed official `easyeda pcb stackup set --layers 6 --plane 15 --plane 18 --signal 16 --signal 17` live in EasyEDA Pro V4.1.97 → **`ok: true, verified: true`**, `copperLayerCount: 6`, `0` DRC `INTERNAL_ERROR`.
  - **Tool Limitation Recorded Honestly**: EasyEDA Pro V4.1.97's `easyeda-agent` CLI (`pcb stackup set`) configures copper layer count and inner layer types (`PLANE`/`SIGNAL`) but does **not** expose physical dielectric thickness editing inside `LAYER_PHYS` (which retains EasyEDA Pro's default `59.449 mil` core placeholder). As proved in PR #43, manually injecting raw `.epcb` `LAYER_PHYS` records causes EasyEDA Pro's native DRC engine to throw `INTERNAL_ERROR`. Therefore, raw `LAYER_PHYS` is intentionally left native and untouched, and the target `0.80 mm` `1+4+1` physical stackup below MUST be entered/confirmed via the contracted PCB fab's Layer Stackup Sheet before Gerber/ODB++ tape-out.

---

## 1. Target Symmetric `0.80 mm` 6-Layer `1+4+1` HDI Stackup Table (`CONDITIONAL`)

| Stackup Layer | EasyEDA Pro Layer ID / Name | Role | Material / Spec | Nominal Thickness (`µm` / `mil`) | Dielectric `Dk` (`@1 GHz`) / `Df` | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **Top Solder Mask** | `5` (`Top Solder Mask`) | LPI Green/Black Matte | Taiyo PSR-4000 (or eq.) | `15 µm` (`0.59 mil`) | `3.5 / 0.020` | `CONDITIONAL` |
| **L1 (Top Copper)** | `1` (`Top Layer`, `SIGNAL`) | Component + RF + High-Speed Escape | `0.33–0.5 oz` base + plating (`~30–35 µm` fin.) | `35 µm` (`1.38 mil`) | — | `CONDITIONAL` |
| **Dielectric 1 (L1–L2)** | `Prepreg 1` | **Laser Microvia Dielectric (`BV_L1_L2`)** | `1 × 1080` (or `1067`) High-Tg FR-4 (`Tg ≥ 170°C`) | **`70–75 µm`** (`2.76–2.95 mil`) | `4.0–4.2 / 0.018` | `CONDITIONAL` |
| **L2 (Inner1 GND)** | `15` (`Inner1`, `PLANE`) | **Solid Reference `GND` Plane** | `0.5 oz` ED Copper | `18 µm` (`0.71 mil`) | — | `PASS` (Topology) / `CONDITIONAL` (Cu) |
| **Dielectric 2 (L2–L3)** | `Core 1` | Inner Isolation Core | High-Tg FR-4 Core (`Tg ≥ 170°C`) | `100 µm` (`3.94 mil`) | `4.2–4.4 / 0.018` | `CONDITIONAL` |
| **L3 (Inner2 Sig)** | `16` (`Inner2`, `SIGNAL`) | Shielded Stripline Signal (`X`-preferred) | `0.5 oz` ED Copper | `18 µm` (`0.71 mil`) | — | `PASS` (Topology) / `CONDITIONAL` (Cu) |
| **Dielectric 3 (L3–L4)** | `Central Prepreg / Core` | Central Structural Prepreg (`2 × 2116` or Core) | High-Tg FR-4 (`Tg ≥ 170°C`) | `220–240 µm` (`8.66–9.45 mil`) | `4.2–4.4 / 0.018` | `CONDITIONAL` |
| **L4 (Inner3 Sig)** | `17` (`Inner3`, `SIGNAL`) | Shielded Stripline Signal (`Y`-preferred) | `0.5 oz` ED Copper | `18 µm` (`0.71 mil`) | — | `PASS` (Topology) / `CONDITIONAL` (Cu) |
| **Dielectric 4 (L4–L5)** | `Core 2` | Inner Isolation Core | High-Tg FR-4 Core (`Tg ≥ 170°C`) | `100 µm` (`3.94 mil`) | `4.2–4.4 / 0.018` | `CONDITIONAL` |
| **L5 (Inner4 GND)** | `18` (`Inner4`, `PLANE`) | **Solid Reference `GND` Plane** | `0.5 oz` ED Copper | `18 µm` (`0.71 mil`) | — | `PASS` (Topology) / `CONDITIONAL` (Cu) |
| **Dielectric 5 (L5–L6)** | `Prepreg 2` | **Laser Microvia Dielectric (`BV_L5_L6`)** | `1 × 1080` (or `1067`) High-Tg FR-4 (`Tg ≥ 170°C`) | **`70–75 µm`** (`2.76–2.95 mil`) | `4.0–4.2 / 0.018` | `CONDITIONAL` |
| **L6 (Bottom Copper)** | `2` (`Bottom Layer`, `SIGNAL`) | Component + BTB + Mic + RF Return | `0.33–0.5 oz` base + plating (`~30–35 µm` fin.) | `35 µm` (`1.38 mil`) | — | `CONDITIONAL` |
| **Bottom Solder Mask** | `6` (`Bottom Solder Mask`) | LPI Green/Black Matte | Taiyo PSR-4000 (or eq.) | `15 µm` (`0.59 mil`) | `3.5 / 0.020` | `CONDITIONAL` |
| **Finished Board Thickness** | **All 3 Boards** | **Target Nominal (`±10%`)** | **Symmetric `1+4+1` 6L HDI** | **`0.80 mm ± 0.08 mm`** (`31.5 mil`) | — | **`CONDITIONAL`** |

---

## 2. Drill-Pair & Aspect-Ratio Verification Matrix

| Drill Pair | EasyEDA Rule / Type | Drill / Pad (`mil` / `mm`) | Dielectric Span | Aspect Ratio | Fab Capability (JLCPCB / PCBWay) | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`BV_L1_L2`** (`L1 ↔ L2`) | `BLIND` (`1 ↔ 15`) | `4.0 / 8.0 mil` (`0.10 / 0.20 mm`) | `70–75 µm` | **`0.70–0.75 : 1`** (`≤ 1:1`) | Laser blind microvia (`0.075–0.15 mm`, AR `≤ 1:1`) | **`CONDITIONAL`** (EDA verified `used=true`; fab laser DFM pending) |
| **`BV_L5_L6`** (`L5 ↔ L6`) | `BLIND` (`18 ↔ 2`) | `4.0 / 8.0 mil` (`0.10 / 0.20 mm`) | `70–75 µm` | **`0.70–0.75 : 1`** (`≤ 1:1`) | Laser blind microvia (`0.075–0.15 mm`, AR `≤ 1:1`) | **`CONDITIONAL`** (EDA verified `used=true`; fab laser DFM pending) |
| **Mech Signal Through** (`L1 ↔ L6`) | `NORMAL` (`1 ↔ 2`) | `6.0 / 12.0 mil` (`0.15 / 0.30 mm`) | `0.80 mm` | **`5.33 : 1`** (`≤ 8:1`) | Mech drill min `0.15 mm`, `0.075 mm` annular ring | **`CONDITIONAL`** (EDA `0` illegal `<6mil` through-vias; fab POFV/ring sign-off pending) |
| **Thermal EPAD Through** (`L1 ↔ L6`) | `NORMAL` (`1 ↔ 2`, `U1` EPAD) | `8.0 / 14.0 mil` (`0.20 / 0.35 mm`) | `0.80 mm` | **`4.00 : 1`** (`≤ 8:1`) | Standard POFV (epoxy-filled & copper-capped) | **`CONDITIONAL`** (Requires POFV cap on `U1` thermal pad) |

---

## 3. Fab Pending Confirmation Checklist (`BLOCKED` / `CONDITIONAL`)

1. **Signed `0.80 mm` `1+4+1` Stackup & `±10%` TDR Impedance Table**: Confirm exact `L1–L2`/`L5–L6` prepreg thickness (`70–75 µm`) and recalculate final `50 Ω` SE RF GCPW (`ANT1`/`ANT2`), `50 Ω` QSPI/48 MHz clock, and `90 Ω` USB FS `D+/D-` trace width/gap before Gerber release.
2. **Fine-Pitch WLCSP DFM Sign-Off**:
   - `U2` (`iCE40UP5K-UWG30`, `0.40 mm` pitch, `0.200 mm` land, `2` `BV_L1_L2` VIPPOs) — confirm `0.40 mm` POFV + NSMD solder-mask bridge (`≥ 0.075 mm`).
   - `U11` (`nRF5340-CMAA`, `0.35 mm` pitch, `0.195 mm` NSMD land, `6.103 mil` copper gap) — confirm Advanced HDI `0.35 mm` WLCSP tier capability (**`BLOCKED`** until signed by contracted fab).
3. **Surface Finish**: Recommend **ENIG** (`2–3 µin` Au over `120–200 µin` Ni) for flat `0.35 mm` / `0.40 mm` WLCSP & `0201` coplanarity — confirm with fab/PCBA house (`CONDITIONAL`).
4. **Compact RF Antenna Keepout (`ANT1`: `5.8×4.2 mm`, `ANT2`: `5.2×4.0 mm` vs Johanson `2450AT18B100E` `6.5×6.5 mm` ref)**: Keep **`CONDITIONAL`** pending real-enclosure VNA `S11` & π-network tuning during `H04` bring-up.
5. **Local SMT Fiducials**: All 3 boards currently carry `1` fiducial mark; add `≥ 2` panel-rail + `≥ 2` local `1.0 mm` non-collinear fiducials at panelization freeze (`CONDITIONAL`).
