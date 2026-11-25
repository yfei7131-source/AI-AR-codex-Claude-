# Rev D1.1 AVDD hardware review — NOT FOR FAB

This is a source-circuit candidate. All physical safety, transient, PVT and JBD sequencing qualifications remain **BLOCKED**. `validate_avdd_safety()` checks circuit identity/connectivity only; it does not certify the product.

## Confirmed inherited failure mechanisms

Rev D1 feeds its idle-HIGH, active-LOW1µs D3 through100k/220nF into EN. A stopped clock leaving D3 HIGH keeps EN charged indefinitely. Gemini94b's positive-pulse peak-hold cannot be copied: idle-HIGH D3 continuously feeds that hold capacitor too. Its quoted diode0.22V and old LDO0.95/0.4V thresholds do not establish guaranteed reset shutdown. D1's charged EN capacitor also discharges through a diode into CRESET_B, creating an injection path into the reset driver/rail. These paths are removed, rather than relabeled.

## Implemented candidate

`SN74LVC2T45DCUR` translates D3 and CRESET from the gated1.8V FPGA domain to VSYS. The B-side nodes have100k pulldowns when translation is isolated. Reference: [TI SCES516N](https://www.ti.com/lit/ds/symlink/sn74lvc2t45.pdf), pin table and power-down section. The exact package is DCU; DIR is tied to VCCA. Both supplies have explicit local bypass.

`LTC6993IS6-2#TRPBF` is rising-edge retriggerable, positive-output. RSET402k1%, DIVCODE4 (1M/392k), NDIV4096 gives32.93184ms nominal. Including1% R and the **3% full-temperature** device bound gives31.624445952..34.258993152ms. The2.3% headline is not substituted for the full-temperature bound. Every completed D3 low pulse retriggers its rising edge. Reference: [ADI LTC6993 Rev F](https://www.analog.com/media/en/technical-documentation/data-sheets/LTC6993-6993-1-6993-2-6993-3-6993-4.pdf), pp2,4–5,10,13–15. S6 pins are TRIG1/GND2/SET3/DIV4/V+5/OUT6. Startup is approximately4.02ms **typical**, with no qualified maximum in this design.

Two `TPS3890` outputs form PG_NODE: `TPS389018DSET` senses FPGA1.8V with MR driven by translated CRESET; `TPS389025DSET` senses VSYS with MR driven by the translated D3 through10k/10nF. Thus normal1µs low pulses do not assert manual reset, but a sustained request-OFF/configuration-low signal does. A third `TPS389025DSET` clamps LDO EN directly on VSYS undervoltage, including the region where the digital buffers are below their operating voltage. It is intentionally separate from PG_NODE, avoiding qualifier-clear deadlock through its own EN clamp. References: [TI SLVSD65A](https://www.ti.com/lit/ds/symlink/tps3890.pdf), pp3,5–6,14. All CT pins are explicitly NC; no undocumented timing capacitor is assumed.

CDONE rising by itself must not enable AVDD. `SN74LVC1G175DCKR` clocks on translated D3 rising edges, with D tied HIGH. Its asynchronous CLR is held low by a10k/100nF arming RC and hard OD clamps until the watchdog and PG are valid. First CDONE rising occurs while CLR is still low. A later completed heartbeat clocks Q HIGH. Loss of watchdog or PG clears qualification. The RC input and PG_NODE are cleaned by the two channels of `SN74LVC2G17DCKR`; a slow RC is never wired directly into a non-Schmitt DFF CLR. References: [TI SCES560G](https://www.ti.com/lit/ds/symlink/sn74lvc1g175.pdf), pp3–7; [TI SCES381N](https://www.ti.com/lit/ds/symlink/sn74lvc2g17.pdf), pp3–6. Arming RC/PVT bounds remain unqualified, including the final capacitor's effective capacitance.

Two `74LVC2G07GS` dual OD packages implement hard qualifier clearing and EN clamping. The **Nexperia** part is deliberately specified, rather than inferring TI output leakage from its input-current specification. Its documented active IOZ and power-off leakage are2µA per output; VOL is0.1V at100µA. Source: [Nexperia74LVC2G07 Rev13](https://assets.nexperia.com/documents/data-sheet/74LVC2G07.pdf), pp2–7. GS is SOT1202 XSON6,1x1x0.35mm. PG_NODE is Schmitt-cleaned before ordinary buffer inputs, avoiding a known slow-edge issue.

WD_Q feeds EN through68k, with330k to GND. EN is clamped by qualification/PG OD outputs and the independent VSYS supervisor. The low supervisor load at0.8V is below15µA. At normal light load, the IOZ bounds and a1µA **design budget** for the LDO EN input give useful HIGH margin. That1µA value is not a vendor full-temperature maximum; it cannot close physical leakage qualification. Source: [TLV755P SBVS320D](https://www.ti.com/lit/ds/symlink/tlv755p.pdf), Table4-1 p3 and electrical characteristics p6: EN VHI1.0V/VLO0.3V, IEN10nA typical. The DQN thermal pad is now explicitly grounded on all seven inherited DQN LDO instances.

## Probe and firmware consequences

TP_AVDD_SAFE exposes D3,CRESET,WD_Q,PG_NODE,qualifier CLR,Q,EN,AVDD and GND. Probe loading/fixture geometry remain a native-layout task. No AVDD output voltage is chosen from JBD's missing NDA information.

The old fixed wait of21ms after CDONE is **retired**. A CDONE/first heartbeat during timer startup may be ignored; a subsequent edge arms the qualifier, and another edge completes qualification. Firmware bring-up must observe actual EN/AVDD or use a subsequently qualified maximum startup bound before JBD initialization. The source does not justify a guaranteed45ms replacement delay.

## Explicit remaining BLOCKED items

- Exact supervisor MR/SENSE maximum response at these rails/loads, timer startup maximum, qualifier RC/leakage/PVT and clock/clear recovery over all asynchronous rearming cases.
- Arbitrarily fast VSYS or FPGA-I/O droops: nominal supervisor propagation is not a bound on how fast power can traverse a safe threshold. Overshoot, ringing, partial power and ground offsets remain bench tasks.
- JBD AVDD value/current/output capacitance and allowed ramp/shutdown/rail order. TLV755P120Ω discharge is typical and cannot prove vendor shutdown timing.
- Nine ICs, explicit passives and fixture pads need native placement/ERC/DRC/assembly and full mass/thermal recheck. Device and passive masses are estimates, not measured savings.
- Final procurement MPNs and capacitor effective capacitance; all package envelopes must be checked against controlled vendor mechanical drawings before native layout. No replacement of the immutable D1 package is performed.
