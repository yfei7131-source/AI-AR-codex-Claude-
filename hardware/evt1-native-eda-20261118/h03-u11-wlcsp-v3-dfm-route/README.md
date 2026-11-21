# EVT-1 H03 — `PCB3 U11` (`nRF5340-CMAA-R7`) WLCSP Route Decision, V3 Extended Blind-Via DFM Audit & Priority-Net Incremental Routing (PR #46)

- **Baseline Inherited**: PR #45 (`hardware/evt1-h03-hdi-laser-wlcsp-route-20261121` @ `a02f7ba`, preserved untouched)
- **Live EDA Verified**: EasyEDA Pro `V4.1.97` (`easyeda-agent v1.17.0`), independent fresh re-import **100% exact match**
- **Release Verdict**: **`NOT FOR FAB` / `BLOCKED`** (see `BLOCKED.md`)

## Key Deliverables
- **Editable Native Archive**: `native/ZY_AIAR_EVT1_H03_3BOARD_U11_V3_DFM_MECR01_NOT_FOR_FAB.epro2`
- **Technical Route Decision & V3 DFM Report**: `U11_WLCSP_ROUTE_DECISION_AND_V3_DFM_REPORT.md`
- **Blocked Manufacturing/Supplier Gates**: `BLOCKED.md`
- **V3 Extended Blind-Via & `U11` WLCSP Auditor + Tests**: `independent_hdi_dfm_auditor_v3.py`, `test_independent_hdi_dfm_auditor_v3.py`
- **Incremental Priority-Net Router & Live Commit Pipeline**: `incremental_route_on_pr45.py`, `apply_pr46_incremental_and_reimport.py`
- **Deterministic CI Verifier & Checksums**: `verify_h03_u11_wlcsp_v3_dfm_route.py`, `verification-report.json`, `SHA256SUMS.txt`
- **Raw Evidence**:
  - `evidence/baseline-pr45-v3-audit/`: PR #45 V3 extended audit baseline (`139` blind microvias, `0` violations)
  - `evidence/delta-plans/`: PR #46 incremental routing delta plans & anti-pad lists
  - `evidence/post-route/`: live post-save/reload dumps, strict DRC JSONs, `pcb check` JSONs, blind-via rule readbacks, export & pipeline receipt
  - `evidence/reimport-verify/`: independent fresh re-import dumps & strict DRC JSONs (100% exact match)
  - `evidence/post-dfm-v3-audit/`: untruncated V3 extended blind-via + 3D conflict matrices (`141` blind microvias, `0` violations)
  - `evidence/erc-3board/`: live 3-board strict ERC (`0` errors/warnings) & `207/207` Protel2 netlists

## Quick Verification
```bash
python3 -m unittest discover -s hardware/evt1-native-eda-20261118/h03-u11-wlcsp-v3-dfm-route -p "test_*.py" -v
python3 -B hardware/evt1-native-eda-20261118/h03-u11-wlcsp-v3-dfm-route/verify_h03_u11_wlcsp_v3_dfm_route.py \
  --root hardware/evt1-native-eda-20261118/h03-u11-wlcsp-v3-dfm-route
```
