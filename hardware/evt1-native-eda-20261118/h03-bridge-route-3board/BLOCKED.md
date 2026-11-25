# EVT-1 H03 Manufacturing Gate & `BLOCKED` Register (`NOT FOR FAB`)

> **Release Verdict: `NOT FOR FAB` — MANUFACTURING REMAINS STRICTLY BLOCKED.**
> Zero Gerbers, drill files, or SMT assembly outputs may be released until every blocker below is closed.

## P0 — Vendor NDA & External Mechanical Blockers (Unchanged — Zero Pinout Guessing)

| ID | Board | Affected Refs | Blocking Condition |
| :--- | :--- | :--- | :--- |
| **BLK-01** | `M-OPT-BRIDGE` | `J2` (`J_DISP_L`), `J3` (`J_DISP_R`) | **JBD 0.13" MicroLED NDA**: exact receptacle MPN, pinout, QSPI/MIPI interface assignment, and mating FPC drawing unconfirmed (Track B/H03 uses provisional `BM28-10+2P` mechanical envelope ONLY for space & routing validation) |
| **BLK-02** | `M-OPT-BRIDGE` | `U6` (`U6_OPT_AVDD`) | **JBD AVDD Rail NDA**: exact nominal voltage, peak current, and power-down timing unconfirmed |
| **BLK-03** | `M-MAIN-L` | `J2` (`J_CAM_FPC`) | **Camera Module NDA**: connector part number, pinout, and FPC exit unconfirmed (left unplaced on `PCB1`) |
| **BLK-04** | `M-MAIN-L` | `J3` (`J_USB_POGO`) | **Mechanical ID Pogo Interface TBD**: spring-pin pitch, contact count, and temple pad coordinates not frozen (left unplaced on `PCB1`) |
| **BLK-05** | `M-MAIN-L`, `M-AUD-R` | `BAT1`, `SPK1` (×2) | **Off-Board Battery & Speaker Harness**: `Convert to PCB = no`; exact temple solder-pad geometry pending ME enclosure freeze |
| **BLK-06** | `M-OPT-BRIDGE` | `MECR-01` (`25.0 × 4.6 mm`) | **ID / ME Structural Approval**: `22.0 × 4.2 mm` remains the untouched baseline in PR #40 (`h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2`); `25.0 × 4.6 mm` remains an independent engineering trial pending formal ID/ME sign-off |

## P1 — H03 Routing Completion & Native EDA Closure Items

| ID | Board | Live EasyEDA Pro V4.1.97 Status | Remaining Closure Work |
| :--- | :--- | :--- | :--- |
| **BLK-07** | `PCB2` (`M-OPT-BRIDGE`) | `0` clearance errors, `0` MK2 errors, `0` Plane Zone errors; **`270` remaining airwires** (`262 SMD Pad + 6 Via + 2 Track`) | Complete routing of remaining QSPI (`opt_l/r_qdo*`, `host_qio*`), AVDD chain, and power buses; inner-ring `U2` BGA signals under locked `6.0 mil` pad-to-track rule require fab-confirmed HDI blind/buried microvias (`L1–L2` / `L1–L3` laser VIPPO) or fab-approved BGA courtyard clearance rule (NOT relaxed unilaterally) |
| **BLK-08** | `PCB1` (`M-MAIN-L`) | `118/118` placed, `0` clearance errors, `0` MK1/RF errors, `0` Plane Zone errors; **`464` remaining airwires** (`459 SMD Pad + 5 Via`) | Execute full signal/power/RF `50 Ω` CPWG (`ANT1`) and USB `90 Ω` diff-pair routing after `J2`/`J3` freeze |
| **BLK-09** | `PCB3` (`M-AUD-R`) | `53/53` placed, `0` clearance errors, `0` MK3/RF errors, `0` Plane Zone errors; **`190` remaining airwires** (`186 SMD Pad + 4 Via`) | Execute full `nRF5340` fanout, `50 Ω` RF matching (`ANT2`), `32 MHz`/`32.768 kHz` crystal guard rings, I2S, and charger routing |
| **BLK-10** | `PCB1`, `PCB2`, `PCB3` | **`1` `Import Changes` (`Netlist Error`) per board** | Run interactive foreground EasyEDA Pro GUI **Import Changes** confirmation (once blocked parts are unfrozen on `PCB1`/`PCB3`) to clear the headless CLI sync flag |
| **BLK-11** | All 3 Boards | Bench & SI/PI/Thermal Verification | Hardware bench scope capture (`AVDD` watchdog, `ECO-02` privacy LED window comparator, `ECO-07` `475.5 mA` USB current limit, `ECO-03` FPGA sequencing) remains `BLOCKED_NO_BENCH_MEASUREMENTS` |
