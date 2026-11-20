# EVT-1 H03 HDI Manufacturing Constraint Closure & Three-Board Routing (`h03-hdi-dfm-route-closure`)

- **Inherited Baseline**: **PR #42** (`hardware/evt1-h03-3board-routing-hdi-20261121`) & **PR #40** (`22.0 × 4.2 mm` Track A untouched)
- **Live EDA Tool**: EasyEDA Pro **V4.1.97** (`easyeda-agent v1.17.0`)
- **Release Gate**: **`NOT FOR FAB` / `BLOCKED`**

## Key Verified Deliverables

| Artifact | Purpose |
| :--- | :--- |
| `native/ZY_AIAR_EVT1_H03_3BOARD_HDI_DFM_MECR01_NOT_FOR_FAB.epro2` | Live-exported editable 3-board native project (`971` persisted lines `100% ≥ 3.0 mil`, `237` true `4/8 mil` `BV_L1_L2`/`BV_L5_L6` laser blind microvias + `45` mechanical through-vias, `0` illegal `4/8` through-vias, `0` clearance/Plane/mic DRC, `686` unconnected = `-64` vs PR #42 / `-238` vs PR #41) |
| `HDI_VIA_STACKUP_DFM_AND_ROUTING_REPORT.md` | Live blind-via layer-span proof, JLCPCB/PCBWay/Johanson capability matrix, PR #41→#42→#43 DRC scoreboard, `Import Changes` diagnosis, independent re-import round-trip proof & 27-item ERC classification |
| `BLOCKED.md` | Explicit resolved-in-EDA vs remaining `BLOCKED` / `CONDITIONAL` tape-out gates |
| `route_3board_hdi_engine.py` | Symmetric `1+4+1` 4-signal-layer (`L1/L3/L4/L6`) Kruskal-Steiner router enforcing `≥ 3.0 mil` traces, `6/12 mil` mechanical signal through-vias, and `BV_L1_L2`/`BV_L5_L6` blind `GND` microvias |
| `apply_hdi_dfm_commit_and_reimport.py` | Live EasyEDA Pro V4.1.97 build, commit, save/reload, DRC/ERC/blind-rule readback, `.epro2` export & independent fresh re-import verification driver |
| `verify_h03_hdi_dfm_closure.py` | Deterministic CI verifier (`verification-report.json`) enforcing zero `< 3.0 mil` tracks, zero illegal `4/8` through-vias, live `used=true` blind microvias, `dump == .epro2 == reimport` parity, `207/207` netlist parity, and untouched Track A `22.0 × 4.2 mm` |
| `evidence/post-route/` | Live post-route dumps, strict DRC JSONs, live `drc-rules` blind-via readbacks, `pcb check` DFM JSONs, `archive-response.json` & `live-pipeline-receipt.json` |
| `evidence/reimport-verify/` | Independent fresh re-import dumps & strict DRC JSONs proving `100%` export→re-import fidelity |
| `evidence/erc-3board/` | Live 3-board strict ERC JSONs & Protel2 netlists (`M-MAIN-L`, `M-OPT-BRIDGE`, `M-AUD-R`) |
| `SHA256SUMS.txt` | Cryptographic manifest of all tracked deliverables |

## Deterministic Verification Command

```bash
python3 -B hardware/evt1-native-eda-20261118/h03-hdi-dfm-route-closure/verify_h03_hdi_dfm_closure.py
```
