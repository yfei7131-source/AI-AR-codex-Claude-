# Rev D1.1 FPGA user-mode safety review — NOT FOR FAB

Baseline: PR #21, `ff7ccf93fb6ebce289e6a262adcea4e77c8d4928`.
Gemini comparison: archived `94b50cf66c149f0b5a613edd8e15f18cd2a0eb15`, actual delta `94b50cf_vs_bb87623.patch`. No Gemini code was cherry-picked.

## Confirmed failure paths

1. Rev D1 writes `opt_pwr_off_h` in the host-SCK domain, but D3 consumed it only through `pwr_off_sync` and `d3_low_q` clocked by `clk_48m`. If that clock stopped while D3 was HIGH, a correctly received `A4 OPT_PWR_REQ=0` could never pull D3 LOW. Its DC RC input remained HIGH indefinitely. This is a source-derived predicted failure. The native baseline-witness run must reproduce it before closure; it is not a silicon measurement.
2. An output-only combinational OFF term is insufficient on its own: OFF followed by ON while `clk_48m` remains stopped could release D3 before the clock sampled the OFF request. The repaired shutdown synchronizer must asynchronously assert and release only through real clock edges.
3. Rev D1 accepted SCAN_EN=1 with OPT_PWR_REQ=0. Its serializer and RAW outputs could remain active after power-off. Rev D1.1 explicitly idles the optical outputs while inhibited and clears the scan request. This is a digital idle guarantee; the missing JBD rail/pin constraints still prevent a physical back-powering or fault-tolerance claim.
4. Restart must not expose frozen serializer values while the power and scan synchronizers settle. The serializer's active predicate now also checks synchronized SCAN_EN and the power inhibit.

Gemini's five-state peak-hold assumes positive VSYNC pulses and, for its missing-VSYNC calculation, a LOW final signal. Rev D1's actual D3 user waveform is HIGH with a 48-clock LOW pulse every 800,000 clocks. An arbitrary clock failure may freeze either phase. A static HIGH cannot be distinguished from healthy average HIGH by Rev D1's RC. Directly copying the positive-pulse peak-hold network neither matches Rev D1's polarity nor proves rejection of stuck-HIGH. The separate Rev D1.1 external liveness/supply supervisor is required.

## Implemented delta

- Existing top-level ports, PCF assignment, default OPT_PWR_REQ=1, command values, framebuffer, FIFO, anti-tearing and RAW payload format remain in place.
- `pwr_off_sync` is a two-stage asynchronous-assert/synchronous-release shutdown chain. Both stages assert when the host OFF bit asserts; deassertion advances through running `clk_48m` edges.
- D3 LOW includes both the host-domain OFF bit and the synchronized shutdown bit. The existing heartbeat/d3 register remains for frame timing and release.
- Optical outputs are clamped to SCK=0, CS_N=1, left/right DATA=0 while inhibited. Shutdown may truncate a transaction. Such truncation is a deliberate fault abort and is not a valid panel command.
- SCAN_EN and RAW_ARM are rejected when the same control word requests power OFF. A new power-ON command does not restore a previously aborted scan automatically.
- RAW is still opaque. An A4-shaped sequence inside an armed RAW transaction remains vendor data; it is not a power-off escape command. Finish/abort RAW via the documented transaction or independent external reset path before issuing a control write.
- The original full-frame TB, PCF and memory primitive simulation model are preserved byte-for-byte. The new safety TB and runner are additional checks.

## Native test contract

Run `make sim-safety`, or `python3 run_rev_d1_1_safety.py` in `03_FPGA_RTL`.

The runner compiles **two separate sources**. It first compiles the immutable Rev D1 RTL with `BASELINE_EXPECT_BUG`; that run must explicitly witness the known stopped-clock OFF failure. A successful witness proves a defect exists and does not certify baseline safety. It then compiles Rev D1.1 and requires the repaired assertions to pass.

The repaired TB covers nine cases: SCAN_EN=0 heartbeat timing; all four combinations of stopped clock level and D3 HIGH/LOW phase including OFF→ON without a clock; rejection of SCAN/RAW while OFF; active scan abort with no phantom restart; retained opaque A4 RAW payload; injected true internal OFF during RAW. The last is an internal control fault injection, not an external command decoded inside RAW.

Missing Icarus/vvp returns exit2 and prints BLOCKED_NATIVE_ICARUS. It never prints a simulated PASS. Actual runner commands, source SHA256 and stdout are retained in native CI artifacts. Full Icarus regression, Yosys synthesis, nextpnr and icetime must still pass on the final commit; this document is not their result.

## Explicit remaining boundaries

Hard CDONE during configuration, hard CRESET_B, CRAM loading, brownout and unpowered I/O are outside this user-mode RTL module. No `$force` of the RTL POR counter is presented as a device-configuration test. Those cases require the separate board/supervisor model and physical qualification.

Neither user RTL nor a same-clock counter can prove shutdown of its own stopped clock. Independent watchdog timing, supply-supervisor thresholds, output leakage, diode/switch transients, rail ordering and JBD discharge/settling requirements remain distinct engineering gates. Deassertion recovery/removal, FPC ground shift and real shutdown waveforms also require device/board verification; a passing fabric STA does not cover every asynchronous or analog path.
