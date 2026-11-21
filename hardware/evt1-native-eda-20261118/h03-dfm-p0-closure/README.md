# EVT-1 H03 DFM P0 Closure & Controlled P1 Routing Package (PR #44)

This package inherits PR #43 (`hardware/evt1-h03-hdi-dfm-route-closure-20261121` @ `8fb2a13`) and delivers full **P0 DFM conflict-matrix decomposition, real manufacturing/reliability defect closure, official 6L `1+4+1` stackup validation, controlled P1 routing, and independent fresh re-import verification** in live **EasyEDA Pro `V4.1.97`**.

> **Status**: `NOT FOR FAB` / `BLOCKED` (Track A `22.0 × 4.2 mm` untouched; `MECR-01` `25.0 × 4.6 mm` independent trial).

## Key Deliverables

| Artifact | Purpose |
|---|---|
| `native/ZY_AIAR_EVT1_H03_3BOARD_DFM_P0_MECR01_NOT_FOR_FAB.epro2` | Live-exported, independently re-import-verified 3-board EasyEDA Pro `V4.1.97` archive (`1,077` tracks `≥ 3.0 mil`, `202` vias incl. `154` true `BV_L1_L2`/`BV_L5_L6` dog-bone blind microvias, `0` strict DRC clearance/plane/mic errors) |
| `DFM_CONFLICT_MATRIX_AND_P0_CLOSURE_REPORT.md` | Full untruncated PR #43 audit (`PCB1: 184, PCB2: 103, PCB3: 78`), `PCB2` object-by-object proof, P0 before/after defect closure (`232 → 0` passive `via-in-pad`, `41 → 0` `<6 mil` track pairs, `2 → 0` `3W` crosstalk, `PCB1 C14/C17` decap relocation), and P1 routing/re-import proof |
| `PHYSICAL_STACKUP_0P80MM_1_4_1_TABLE.md` | Target `0.80 mm` 6L `1+4+1` HDI dielectric/copper stackup table, official `pcb stackup set` verification record, and `CONDITIONAL` fab confirmation checklist |
| `BLOCKED.md` | Complete `BLOCKED` / `CONDITIONAL` fab, VIPPO, antenna, MECR-01, and NDA interface gates |
| `independent_hdi_dfm_auditor.py` & `test_independent_hdi_dfm_auditor.py` | Untruncated 3D blind-via-aware `.epcb` DFM auditor + `4/4` passing regression unit tests |
| `route_3board_p0_dfm_engine.py` & `apply_p0_dfm_commit_and_reimport.py` | Reproducible P0-clean 4-signal-layer router and live EasyEDA Pro commit/export/re-import pipeline |
| `verify_h03_dfm_p0_closure.py` & `verification-report.json` | Deterministic CI verifier asserting all untouched baselines, `.epcb` copper/via/decap/3D-audit invariants, re-import parity, `207/207` netlist parity, and zero path leaks |
| `evidence/pr43-baseline-audit/` & `evidence/post-dfm-audit/` | Untruncated before/after object-by-object CSV conflict matrices and JSON summaries |
| `evidence/post-route/`, `evidence/reimport-verify/`, `evidence/erc-3board/` | Raw live EasyEDA Pro `V4.1.97` dumps, strict DRC, `pcb check`, blind-via rule readbacks, independent re-import captures, strict 3-board ERC, and Protel2 netlists |

## Local Verification Commands

```bash
python3 -m unittest discover -s hardware/evt1-native-eda-20261118/h03-dfm-p0-closure -p "test_*.py" -v
python3 -B hardware/evt1-native-eda-20261118/h03-dfm-p0-closure/verify_h03_dfm_p0_closure.py \
  --root hardware/evt1-native-eda-20261118/h03-dfm-p0-closure \
  --out hardware/evt1-native-eda-20261118/h03-dfm-p0-closure/verification-report.json
```
