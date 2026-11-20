# EVT-1 H03 Three-Board Routing & 6-Layer HDI Fabrication Audit (`h03-3board-routing-hdi`)

- **Inherited Baseline**: **PR #41** (`hardware/evt1-h03-bridge-route-3board-20261120`) & **PR #40** (`22.0 × 4.2 mm` Track A untouched)
- **Live EDA Software**: EasyEDA Pro **V4.1.97** (`easyeda-agent v1.17.0`)
- **Release Gate**: **`NOT FOR FAB` / `BLOCKED`**

## Key Verified Deliverables

| Artifact | Purpose |
| :--- | :--- |
| `native/ZY_AIAR_EVT1_H03_3BOARD_ROUTED_MECR01_NOT_FOR_FAB.epro2` | Live-exported editable 3-board native project (`1,233` persisted copper lines, `135` persisted vias, `0` clearance / `0` Plane Zone / `0` acoustic errors across `PCB1`/`PCB2`/`PCB3`; `-174` unconnected records vs PR #41) |
| `PR41_DATA_AUDIT_AND_3BOARD_ROUTING_REPORT.md` | Exact per-net forensic explanation of PR #41 `340 → 323` tracks, PR #41 → PR #42 before/after DRC & airwire reduction scoreboard, `207/207` Protel2 netlist parity, and per-item classification of all `27` Track A strict ERC items |
| `HDI_6L_FAB_CAPABILITY_AND_CONDITIONAL_MATRIX.md` | Real published JLCPCB / PCBWay 6L HDI & Johanson `2450AT18B100E` capability audit (`2.5 mil` trace, `4/8 mil` laser blind microvia vs `0.15 mm` mech through-drill, `0.35 mm` WLCSP VIPPO, impedance, compact antenna keepouts marked `CONDITIONAL`) |
| `BLOCKED.md` | Explicit manufacturing & NDA interface blockers (`J2/J3/U6` JBD NDA, `J2` Camera NDA, `J3` Pogo, `BAT1`/`SPK1` off-board, remaining airwires, `MECR-01` ID/ME sign-off) |
| `route_3board_engine.py` | Union-Find Kruskal-Steiner Forest + 2-pass same-layer GND chaining router with exact `r = 15.2 mil` L2/L5 anti-pad planner for `PCB1`, `PCB2`, `PCB3` |
| `apply_3board_antipads_and_commit.py` | Live EasyEDA Pro V4.1.97 commit, save/reload, strict DRC, strict 3-board ERC, and official `.epro2` export driver |
| `verify_h03_3board_routing_hdi.py` | Deterministic CI verifier (`verification-report.json`) checking archive SHA256, `dump == .epro2` copper parity, `0` clearance/plane/mic DRC, airwire reductions on all 3 PCBs, `207/207` netlist parity, and untouched Track A `22.0 × 4.2 mm` baseline |
| `evidence/post-route/` | Live post-route dumps (`PCB{1,2,3}-post.dump.json`), strict DRC JSONs (`PCB{1,2,3}-drc-post.json`), `archive-response.json`, and `live-pipeline-receipt.json` |
| `evidence/erc-3board/` | Live 3-board strict ERC JSONs and Protel2 netlists (`M-MAIN-L`, `M-OPT-BRIDGE`, `M-AUD-R`) |
| `SHA256SUMS.txt` | Cryptographic manifest of deliverables |

## Structural Baseline Policy

- **Track A (`22.0 × 4.2 mm`)** in `../h02-fp-h03-pcb/native/ZY_AIAR_EVT1_H02_FP_CONV_22x4_2_NOT_FOR_FAB.epro2` is **strictly untouched**.
- **Track B (`25.0 × 4.6 mm`, `MECR-01`)** remains an **independent engineering trial** and may not replace the official mechanical baseline without formal ID/ME approval.

## Deterministic Verification Command

```bash
python3 -B hardware/evt1-native-eda-20261118/h03-3board-routing-hdi/verify_h03_3board_routing_hdi.py
```
