# EVT-1 Manufacturing Gate & `BLOCKED` Register (`NOT FOR FAB`)

> **Release Verdict: `NOT FOR FAB` — MANUFACTURING REMAINS STRICTLY BLOCKED.**
> No fabrication Gerbers, drill files, or SMT pick-and-place outputs may be released until every P0 blocker below is closed with vendor documentation and clean native DRC/ERC.

## P0 — Vendor NDA & External Mechanical Blockers (Carry-Over, Unchanged — Zero Guessing)

| ID | Scope | Affected Refs | Blocking Condition | Required Closure Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **BLK-01** | `M-OPT-BRIDGE` | `J2` (`J_DISP_L`), `J3` (`J_DISP_R`) | **JBD 0.13" MicroLED NDA**: exact receptacle part number, pinout, QSPI/MIPI interface assignment, and mating FPC keepout unconfirmed (Track B uses provisional `BM28-10+2P` mechanical envelope ONLY for space verification) | Signed JBD datasheet & official FPC mechanical drawing |
| **BLK-02** | `M-OPT-BRIDGE` | `U6` (`U6_OPT_AVDD`) | **JBD Optical AVDD Rail NDA**: exact nominal voltage, peak current, ramp/power-down sequence, and package unconfirmed | JBD power-sequencing spec + bench AVDD watchdog timing verification |
| **BLK-03** | `M-MAIN-L` | `J2` (`J_CAM_FPC`) | **Camera Module NDA**: sensor/module connector part number, pinout, and FPC exit angle unconfirmed | Camera module vendor datasheet & mating connector spec |
| **BLK-04** | `M-MAIN-L` | `J3` (`J_USB_POGO`) | **Industrial Design / Mechanical TBD**: temple magnetic pogo pin pitch, pad count, and ESD entry geometry not frozen | Frozen ID/ME STEP model & pogo spring-pin drawing |
| **BLK-05** | `M-MAIN-L`, `M-AUD-R` | `BAT1`, `SPK1` (×2) | **Off-Board Electro-Acoustic & Battery Harness**: marked `Convert to PCB = no`; exact wire-solder pad geometry on left/right temple PCBs pending ME enclosure freeze | Temple enclosure STEP + battery/speaker harness drawing |

## P1 — H03 Bridge PCB (`25.0 × 4.6 mm` `MECR-01` Trial) Routing & Native DRC Blockers

| ID | Metric (Live EasyEDA Pro V4.1.97) | Root Cause | Concrete Closure Action |
| :--- | :--- | :--- | :--- |
| **BLK-06** | **`251` remaining `SMD Pad` + `15` `Via` `Connection Error`s** | Partial routing complete (`185` tracks, `45` vias, `55` pad connections + `2` plane zones closed); remaining nets include `U2` inner BGA balls (`0.40 mm` pitch), QSPI optical buses (`opt_l_qdo*`, `opt_r_qdo*`), host QSPI, I2C, and remaining `VSYS`/`1V8_FPGA_IO`/`GND` pads | Enable 6L HDI laser blind microvias (`L1–L2` / `L1–L3` VIPPO) + `U2` BGA fanout courtyard rule (`2.5–3.0 mil` track-to-pad inside U2 courtyard), complete routing of all 58 nets to `0` airwires |
| **BLK-07** | **`32` `Plane Zone to Via` + `32` `Hole to Plane Zone` Clearance Errors** | `16` non-GND signal through-vias pass through `L2` (`Inner1`) and `L5` (`Inner3`) static `LAYER_FILL` polygons; CLI `pcb pour-rebuild` does not regenerate EasyEDA static negative-plane anti-pads headless | Run interactive `Shift+B` (Rebuild All Copper/Planes) in EasyEDA Pro GUI after full routing so `10 mil` anti-pads are cut around all non-GND vias (`29` GND vias already have `0` plane errors!) |
| **BLK-08** | **`7` Clearance Errors around `MK2` GND Polygon Ring** (`1` `SMD Pad to Track`, `3` `SMD Pad to Via`, `3` `Hole to SMD Pad`) | Only `2` vias (`e32` on `AVDD_WD_DIV`, `e40` on `VSYS`) + `1` stub (`e46`) skirted `MK2`'s non-rectangular polygon GND ring (`e37e14`/`e37e15`); all other `85/86` components have **`0`** clearance errors | Nudge vias `e32` & `e40` by `~8 mil` outside `MK2` outer polygon ring during full H03 routing pass |
| **BLK-09** | **`1` EasyEDA `Import Changes` (`Netlist Error`)** | Verified **`0` diffs** on `86/86` components, `86/86` UniqueIDs, `86/86` Channel IDs, `86/86` footprints/devices, and `328/328` pad nets vs live `.enet`; headless `pcb import-changes` returns `confirm="no-dialog"` on multi-sheet hierarchical board | Execute foreground EasyEDA Pro GUI **Import Changes** confirmation (without shifting component coordinates) to clear internal sync flag |
| **BLK-10** | **`MECR-01` Structural Sign-Off (`22.0 × 4.2 → 25.0 × 4.6 mm`)** | `25.0 × 4.6 mm` is proven feasible (`86/86` placed, `+0.03 g`) in independent Track B copy, while Track A preserves `22.0 × 4.2 mm` | Obtain formal ID/ME nose-bridge CAD sign-off before promoting `25.0 × 4.6 mm` to production baseline |

## P2 — Main & Right Audio Board H03 Layout + Bench Verification

- `PCB1` (`M-MAIN-L`) and `PCB3` (`M-AUD-R`) physical placement, RF `50 Ω` CPWG matching (`ANT1`/`ANT2`), thermal dissipation analysis, and full 3-board SI/PI/DFM checks remain pending H03 Main/Audio phases.
- Real hardware bench validation (`AVDD` watchdog transient scope capture, `ECO-02` privacy LED window comparator fault injection, `ECO-07` `475.5 mA` USB current-limit thermal soak, `ECO-03` FPGA `1.2V → 1.8V` rail sequencing) remains `BLOCKED_NO_BENCH_MEASUREMENTS` until EVT-1 PCBA bring-up.
