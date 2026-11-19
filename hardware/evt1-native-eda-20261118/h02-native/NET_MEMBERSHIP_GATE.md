# H02 native net-membership gate

PR #32 supplies the controlled terminal and part data. For each board, the gate compares the native schematic net groups against the controlled member sets. A native group is one complete Protel2 net block, regardless of its printed label. Two blocks with the same label remain two groups. Missing pins, extra pins, duplicate membership, split nets and merged nets all fail the partition check. A bijective partition with changed compiled names reports the affected native group IDs and remains a name-parity failure.

| Scope | Main left | Optical bridge | Audio right |
| --- | ---: | ---: | ---: |
| All schematic terminals, including NC and externals | 524 | 315 | 236 |
| Conducting board terminal members | 494 | 294 | 183 |
| Native board net groups expected | 110 | 56 | 35 |

The native Protel2 schematic export can include an external BAT1 or speaker with `Convert to PCB no`. Its expected pins must match the complete schematic graph. The separate physical-board projection checks every `Convert to PCB` flag against the controlled part and then excludes the external members. The board ID remains part of the scope for both BAT1 instances and every repeated net name. Protel2 membership checks schematic compilation. PCB pads and copper continuity require their own checks.

PR #31 and PR #33 pass the label and NC comparison when each page is viewed independently. The native page-parent registry fails, and neither historical return supplies three coherent board netlists. PR #33's selected evidence comes from different capture points. Against PR #32, its 172/233 literal manufacturer-field matches include generic resistors/capacitors and grouped source descriptions. Of 53 instance-level order-code candidates, 42 exact fields match. L2 still carries DFE161212U-2R2M and conflicts with the controlled DFE21CCN2R2MELL. Missing or unqualified source selections remain BLOCKED even when generic text was copied. A KiCad footprint string also does not prove a native footprint UUID or qualified physical land.

## Readback files

- Keep `board_pages.json` and the raw typed `lceda-boards.json`, `lceda-pages.json` and `lceda-pcbs.json` registries. Record three board names, each distinct schematic/PCB document, and exact parent page membership.
- On each verified root, capture `easyeda sch netlist --type Protel2`. Copy the output byte-for-byte to `board-netlists/<board>.net` and the raw response `<board>.protel2.response.json`. The checker verifies project/page, artifact ID/kind, byte count and SHA256 before reading any net group. If the result is only the active page, the expected board-wide group membership will be incomplete.
- Capture raw `board-boms/<board>.csv` and `<board>.response.json`. Save each page's `sch/<page>.json` connectivity and `pins/<page>.json` component and NC records. Save strict ERC with raw project/page provenance. Keep save, reload, and archive exports and restoration evidence for the final acceptance review.

Use `python verify_h02.py --schematic <capture-directory> --output <result.json>`. The status applies to the supplied packet. A clear electrical result remains subject to coherent save/reload and restored archive proof, actual footprint approval, H03 and manufacturing gates.

[EasyEDA native manufacture netlist API](https://prodocs.easyeda.com/en/api/reference/pro-api.sch_manufacturedata.getnetlistfile.html) · [Native Protel2 export example](https://prodocs.lceda.cn/en/api/guide/cli.html)
