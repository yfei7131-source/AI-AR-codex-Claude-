# ZY AI/AR H02/H03 R5 S0–S6 r4 — GitHub Upload Handoff

**Status:** Editable EVT-0 PCB design candidate. **NOT FOR FAB.** This directory contains the actual Claude handoff files copied from the user-provided S6 archive; it is not a KiCad-validated manufacturing release.

- Main KiCad project: `hardware/evt0-r5-rework/evt0_core/evt0_core.kicad_pro`
- PCB SHA-256: `c0f1ca5cfd155328726e63b1a7c2d5090ea79e82156db8b7f6d6bf5673764477`
- Schematic SHA-256: `81d599e6d107563f43d2521262fd50ffaea25e8457332b169c59d1ca32a142e6`
- Inherited PR#4 head: `b1699dd42d7b44ce89d61d20f49b40898d3855f0`
- Existing R4 and R5 experimental historical directories are unchanged.
- Offline connectivity selfcheck: 51 unconnected, 0 dangling; **not native DRC**.
- Native KiCad ERC, DRC, schematic parity and In1/In2 zone refill: **NOT RUN**. Keep all native checks and production release blocked.
- USB DP/DM routing blocked pending controlled stackup, 90Ω differential impedance and manufacturer constraints.
- Source handoff: `hardware/claude_handoff/2026-11-13-s6-r4/STATE_FOR_NEXT_SESSION.md` (section VI is latest).
- Before hardware work, run native KiCad checks on a working COPY, save reports, compare source hashes.

Do not merge automatically. This branch exists to preserve editable project artifacts and historical evidence for subsequent Codex/Claude verification.
