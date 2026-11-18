# EVT-1 H03 PCB design inputs — NOT FOR FAB

Use `PCB_CONSTRAINTS.json` to carry forward the PR #25 board envelopes, HDI minimums, escape candidates, and inter-board current assumptions. Use `FOOTPRINT_MAP.csv` to join the effective source tables by `Board` and `RefDes`. A footprint row is **PASS** when the nominated KiCad library package and the effective numbered copper pads match. Supplier approval, exact passive order codes, mask/paste process, installed fit and electrical margin remain **UNVERIFIED**. A blank footprint is **BLOCKED** and requires the closure in that row.

| Board | Layout starting point | Required for review |
| --- | --- | --- |
| M-MAIN-L | 46 mm left temple, 5.8 / 8.2 / 5.8 mm stepped width, nominal 0.63 mm PCB | Establish ESP32 escape and antenna launch first. Reconcile connector mating, switching loops, protected battery, camera isolation, privacy Kelvin routing and exposed USB/charge entry. |
| M-OPT-BRIDGE | 22 × 4.2 mm bridge, nominal 0.50 mm PCB | Reserve both optical wings, then establish FPGA escape, ASADV oscillator, bypass and AVDD inhibit area. Close mated connector collision, actual IMU and center microphone aperture. |
| M-AUD-R | 34 × 5.2 mm right temple, nominal 0.63 mm PCB | Establish CMAA ball escape and Nordic RF layout, including matching components and crystal. Reconcile right charger, antenna, BTL wire lands, microphone aperture and SWD access. |

## Stack and escape

- Use the inherited six-layer 2+2+2 copper-filled stacked VIPPO process class, 50 μm trace and spacing, 75/180 μm microvia drill/land, 200/400 μm buried via drill/land, 0.25 mm edge clearance and 0.20 mm courtyard gap. Supply three board stack assignments with supplier approval. The inherited layer table sums to 0.628 mm against a 0.50 mm bridge target. The bridge lamination and impedance stack are **BLOCKED** pending a qualified cross-section that preserves the minimum rules.
- At 350 μm pitch and 180 μm land, a 50 μm route with two 50 μm spaces leaves 20 μm nominal residual. At 400 μm pitch and 200 μm land, it leaves 50 μm. These are **UNVERIFIED** layout margins before tolerances. Return real CAD cross-sections at the tightest escape, the via stack report and supplier process limits.
- Export actual courtyard, copper, mask and paste layers for every fine-pitch assignment. Validate pattern indices against top view, reflected B-side placements and any vendor ball map given as bottom view. Check all distinct power and thermal pads and each intentional NC. Freeze the exact order code where a change could alter the mechanical land.
- Treat each inner reference plane and its return transitions explicitly. Use supplier-derived RF and USB impedance geometry and document RF keepout copper/mask by layer. Keep the tuning pads accessible. Retain short continuous returns to the reference plane through the optical QSPI branches.

## Flex, contact and enclosure

- Keep pad, via, component and stiffener transitions outside active flex bends. Overlay the folded and unfolded FPC in the native STEP assembly, with tolerances around connectors, optics, shell, antenna, battery and microphone seals. Recheck stiffener allowance, bend radius and fatigue data against the FPC vendor construction.
- Preserve PWR1 for VBAT_R_RET and PWR2 for the main ground return. The 0.45 A VSYS bridge estimate divides evenly into 0.225 A actual per P2/P3. With a 1.25 factor and 0.3 A rating, each contact must stay at or below 0.24 A actual. Unequal current-sharing margin is only 15 mA/contact at the estimate. Check via, trace and FPC resistance, temperature and strain tolerances. Confirm the right P2 ground contact cannot become the main return.
- Reserve two optical FPC corridors and module bays. JBD contact mappings, addressing, initialization, AVDD load and timing, and optical STEP remain **BLOCKED** under BLK-JBD-01 through -05. The board-side interface points may remain visible in the review CAD with the gate open.
- Use the 46 mm left board as the active envelope and take zero mass credit for proposed 41.6 mm shortening. Return actual PCB panel dimensions and mass inputs after all parts and service access are placed. Keep bridge safety components, both optics, antennas and fold clearance in the mass and fit accounting.

## KIMI return for H03

1. Return native editable PCB projects, complete footprint libraries or pinned library references, source project revisions, mechanical outline/datum sources, stack approvals and per-board impedance assumptions.
2. Return placement maps with active and mating layers, courtyard collision output, STEP exports and an annotated clearance review for flex, shell, protected packs, both optical bays and acoustic apertures.
3. Return CAD netlist diffs against the effective tables, full ERC and DRC raw logs, applicable manufacturing checks, and an exception register. A clean DRC on a partial board leaves the unplaced/unrouted scope **BLOCKED**.
4. Return the as-routed assessment of the AVDD safety probe accessibility, camera sense Kelvin pair, RF matching, key rails/contact drops and flex returns. Reserve separate results for measured AVDD timing, brown-out and recovery, thermal, battery, RF and mass.

For the reproducibility check, run `python tools/build_pcb_constraints.py --check` and `python tools/build_footprint_map.py --libraries <KiCad footprints directory> --check` from the EVT-1 package. **PASS** is scoped to regenerated constraint data and populated copper-pad matches. **FAIL** exposes a check mismatch. ID/FPC inputs, supplier qualification, incomplete footprints, routed DRC and fabrication release retain their separate **BLOCKED** or **UNVERIFIED** states.
