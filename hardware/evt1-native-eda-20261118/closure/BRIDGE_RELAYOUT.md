# H03 Bridge PCB — BLOCKED / NOT FOR FAB

The PR #30 EasyEDA archive, restored board and final native readback give the same ten candidate body envelopes and pad geometry. The active 22 × 4.2 mm outline still fails geometry. This gate preserves the 0.20 mm placement gaps and the stronger 10 mil (0.254 mm) live copper-to-edge rule. The checker independently confirms the existing U8 collision and quantifies three connector body errors.

| Item | Measured / manufacturer evidence | Disposition |
| --- | --- | --- |
| U8 / U_AVDD_LS | Restored BOTTOM bounds x 0.872–3.088 mm and y 0.309–4.382 mm intersect the J_BRIDGE_IN reserve. Historical TOP 0° has 3.8481 mm copper span across a 3.6920 mm usable width. | Reject both observed poses. Native TOP 90° search requires moving U9, or BOTTOM 90° requires moving MK2. Both affect physical constraints that remain open. |
| U10 / U_AVDD_QUAL | Real audit-board geometry gives 54 independent TOP anchors when the D3 body is absent, and zero after protecting the baseline 0603 envelope. | Keep D3 nominal body and lightpipe zone protected. |
| U14 / U_AVDD_WD | Real audit-board geometry gives zero fixed-neighbor clearance anchors across the bounded TOP/BOTTOM 0° and 90° search, with and without the D3 body. | Repack the whole AVDD group with a relocated neighbor or use a qualified smaller package. |
| J_DISP_L/R | Actual Hirose receptacle body is 4.35 × 1.70 × 0.60 mm. The long axis overhangs the 4.20 mm board by 0.15 mm total in the original transverse position. Long-axis Y at original centers collides with U13/D3 left and U7 right. | Rework both connector and FPC orientations together, keeping independent binocular branches. Require approval of the lightpipe, optical modules and mated FPC geometry. |
| J_BRIDGE_IN | Actual Hirose receptacle is 7.85 × 1.70 × 0.60 mm, 1.30 mm longer than the previous 6.55 mm reserve. At original Y=3.60, the bare body extends 0.325 mm beyond the end. With fixed Y1, the unobstructed pre-clock length is 7.5219 mm. Bypass corridors either side of Y1 are 0.2893 mm and 1.0887 mm, narrower than the bare 1.70 mm body. | A longitudinal shift within the original entry end cannot clear the local clock. Repartition the bridge trunk mating interface or obtain a shorter verified implementation with identical electrical contact obligations. |

The manufacturer values are bare receptacle dimensions. Mated plugs, lands, tolerance, insertion access, mechanical envelope, dynamic flex, and all panel-side NDA assignments remain separate gates. [Hirose 10-position receptacle](https://www.hirose.com/en/product/p/CL0673-5044-0-53) · [Hirose 30-position receptacle](https://www.hirose.com/en/product/p/CL0673-5021-0-53)

## Implementation order for KIMI

1. Keep U2_FPGA and Y1_OSC local on the bridge. Preserve B3 clock access, bypasses at the actual supply balls, short supply/ground loops and the copper-filled VIPPO process. Release a changed clock placement only with source pad map, native stack/routing and SI/PI review.
2. Obtain the mated board-to-board model, land/pin-1 drawings and folded/unfolded FPC stack. Study moving the detachable joint to an adjacent ID-approved rigid support with a strain-relieved electrical link to the bridge. Keep PWR1/PWR2 dedicated to VBAT_R_RET/GND and VSYS P2/P3 sharing, verify temperature, IR drop and current return under worst load, and prove continuity for the rest of the contract. Keep the alternative uncommitted until mechanical and electrical reviews agree.
3. Keep the optical pair and privacy aperture reserved. The design-adjustment envelope puts the 10-way bodies along Y with centers (2.10, 4.20) and (2.10, 14.80) mm, and exposes the required U13/U7 and D3 relocations. Obtain ID approval for the relative panel/FPC/connector/lightpipe changes. If these cannot move, return an independently supported narrower interface after JBD clearance. Do not assign a panel-side pin or alter D3 electrical behavior.
4. Repack the bridge functions as groups after choosing the connector path. Place U_AVDD_LS with both supply bypasses and FPGA CDONE/VSYNC and CRESET_B. Keep AVDD_D3_VSYS close to watchdog TRIG and qualifier CLK, keep SET/DIV local, keep AVDD_QUAL_CLR_N and its qualification and clear network short, and keep U_AVDD_SYS_CLAMP and open-drain disable connected directly to OPT_AVDD_EN near the candidate LDO. Keep the test return adjacent to the safety-probe points. Keep U9's axes and MK2's physical sound port/gasket unless ID signs off a change. The U10 geometric case that displaces U2 is excluded from implementation.
5. If the DCU translator still cannot fit, evaluate TI SN74LVC2T45YZPR. The YZP0008 drawing gives 0.918 × 1.918 mm maximum body and 0.50 mm pitch. The DCU→YZP pin-function correspondence is 1→A1, 2→B1, 3→C1, 4→D1, 5→D2, 6→C2, 7→B2, 8→A2. This candidate remains **BLOCKED** pending exact order-code land/paste/mask, escape and AVDD behavior verification. [TI part and drawing](https://www.ti.com/product/SN74LVC2T45/part-details/SN74LVC2T45YZPR) · [TI Table 4-1/4-2 and package outline](https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf)

The machine-readable [bridge evidence](evidence/bridge_placement.json) records input SHA256s, exact native reservations and bounding boxes, all search counts, and measured anchors in millimetres. Each `sampleNativeAnchorMm` is an independent one-component witness against the original reservations plus the D3 body. Coordinates are in the native unmirrored board axes and reference the footprint origin. A fresh native snapshot is required after any approved mechanical change.

## Reproduction

```text
python check_bridge_placement.py --check
python check_bridge_placement.py --check --strict
python -m unittest -v test_bridge_placement
```

The deterministic evidence check passes. Strict mode exits 1 on the observed geometry failure. PCB placement, complete interconnect, native DRC, installed STEP fit and manufacturing remain **BLOCKED**.
