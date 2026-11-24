# Gemini Neon Round 3 — H03 research handoff

Status: RESEARCH ONLY / NOT FOR FAB. Native project baseline: PR #58, commit 1b69c06e81500d6a8b5ce4aaf268513c6b89dfd4. Related research: PR #56 and #57. This archive does not modify the native design or approve manufacture.

- neon-1 (Neno0): controlled ECO patch; audit inputs were reconstructed, not full original records. Candidate only.
- neon-2 (Neno1): reported L2-L3 blind/buried via persistence; trial introduced two plane-clearance errors and was rolled back. Native replay, antipad/return-path design and written fabricator EQ remain blocked.
- neon-3 (Neno2): older cloud clone, 134 -> 135 -> 134 connection errors; do not replace PR #58 PCB3 (130 errors). K5-to-L9 ECO is a candidate only; firmware overlay not build-verified.
- neon-4 (Neno3): remote browser file-import policy blocked native interface work.
- neon-5 (Neno4): fixture-based geometry tests pass; actual R7/R8 PCB2 copper JSON fails schema parsing. Do not accept proposed C11 coordinates without real-data and native DRC verification.

R8 baseline: PCB1/2/3 connection errors 339/232/130 (701 total), six ERC fatal, one netlist difference. Preserve dual-eye transparent AR, 40 g target, and controlled manufacturing/safety rules. No merge or fabrication.

The remaining original files, source mapping and SHA-256 manifest are to be uploaded together using the verified local Git package. Full archive acceptance requires matching the remote tree to the original-file manifest.
