# EVT-1 H03 · Gemini Neno0–4 / R10 round 5 archive

**RESEARCH ONLY / NOT FOR FAB — 未合并，未通过原生工程验收。**

- Native integration checkpoint: PR #62 / `59fb25511ad82649d26de0016137bb2e18c4332d` (689 connection errors, 6 ERC fatal, 1 netlist difference as reported by Codex).
- Candidate input provenance: PR #60 / R9 `a825953d62603624d2ad5105d223d07b87ba8d05`; earlier research PR #61 / `d5c2cf19acbadd5ae1e16fbadfbf1199b0f3628a`. R9-based outputs must not be described as R10-native results.
- Suggested independent branch: `hardware/research/neon-r10-round5-20261124`, based on PR #62. Draft PR only; no merge, no fabrication, no changes to the native master.

## Contents and admission gates

| Window | Scope | Status / next gate |
|---|---|---|
| Neno0 | PCB1 batch routing | Candidate EPRO2 and routing scripts; independently replay and check physical net rules, actual plane geometry and native ERC/DRC. |
| Neno1 | PCB3 U11 K4 HDI | Candidate incremental data and scripts; verify real layer spans, antipads, ground return and fabrication constraints. |
| Neno2 | PCB3 joint placement and routing | Latest offline delta and solver; check overlap with Neno1, isolate ECO and non-ECO candidates; validate power widths and reference planes. |
| Neno3 | PCB1 J2/J3 footprints | Latest footprint package plus supplementary and earlier data; verify U12 physical pin mapping against original datasheet and native project; no unverified symbol/footprint binding. |
| Neno4 | PCB2 C11 relocation / VSYS | Latest offline solver and tests; complete end-to-end layer transitions and real plane return, validate widths and manufacturing. |

Initial blocked screenshots are retained as provenance. Source claims and predicted error reductions are not native validation. This archive does not change the master project or authorize fabrication. Keep real binocular transparent AR, 40 g target, existing safety and manufacturing rules. Any unsupported item remains BLOCKED.

## Integrity

`SOURCE_MAP.json` maps all original leaf artifacts and exact duplicates. SHA256SUMS covers every file except itself. Compare the unpacked local archive directory with the final remote Git tree; do not report sync complete until the remote commit and exact content are verified.
