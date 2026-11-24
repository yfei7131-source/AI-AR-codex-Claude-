# Gemini Neon Round 4 — H03 research handoff

RESEARCH ONLY / NOT FOR FAB. Original research inputs: PR #58 / R8 (1b69c06e81500d6a8b5ce4aaf268513c6b89dfd4); archive branch is based on Codex R9 after its verified upload. Research provenance remains R8; do not present it as R9-native work. Related PR #59 (Round 3).

- neon-1/Neno0 and neon-2/Neno1: overlapping ECO patch work; conflicting U12 status/footprint and incomplete catalog counters/NC review. Candidate only. No HDI deliverable in neon-2.
- neon-3/Neno2: PCB3 placement/routing proposals; U10 candidate collides with existing components; pad/anchor coordinate mismatch. Reject direct application. No native project.
- neon-4/Neno3: J3 narrow target connector with independent enclosure magnets, candidate Mill-Max 856-10-004-30-051000; supplier/assembly/polarity/ESD and J2 FPC confirmation remain blocked.
- neon-5/Neno4: actual R7/R8 JSON parser and tests; S2 candidates pass limited offline screening only. Missing plane geometry, layer spans and complete endpoints/return paths require native verification. No native DRC pass.

R9 candidate baseline: PCB1/2/3 334/232/129 connections (695 total), ERC fatal 6, netlist difference 1. R9 HDI test is isolated and netless, not a manufacturing approval. Preserve real dual-eye transparent AR, 40 g target, safety and manufacturing rules. No merge or fabrication.

25 original distinct files preserved byte-for-byte (24 nested + one byte-different outer script variant); identical outer copies mapped in SOURCE_MAP.json. SHA256SUMS.txt covers all other files.
