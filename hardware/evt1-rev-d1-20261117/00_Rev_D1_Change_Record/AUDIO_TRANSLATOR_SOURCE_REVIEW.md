# Rev D1 audio and translator source review — NOT FOR FAB

Date: 2026-11-17. Scope: engineering CSV/JSON connectivity, vendor pin identity and DC calculations. No CAD persistence, routing, DRC, SI simulation, oscilloscope, acoustic or physical mass test is claimed.

## Primary evidence read

| Device | Primary document and location | Used for |
|---|---|---|
| SN74AXC8T245 RJW | [TI SCES875C](https://www.ti.com/lit/ds/symlink/sn74axc8t245.pdf), pp2–3 Table4-1 and RJW top-view; p6 DC; pp20–23 operation/application; RJW0024A drawing | Physical24-pin map, dual VCCB/GND pins, DIR banks, OE referenced toVCCA, Ioff and VCC<100mV isolation, 100nF bypass |
| SN74AXC4T245 RSV | [TI SCES877B](https://www.ti.com/lit/ds/symlink/sn74axc4t245.pdf), p4 Table4-1; supply/operation/application sections; RSV0016A drawing | Physical16-pin map; independent two-channel banks; GND10/11; OE1/16; 2.6x1.8mm body |
| PCA9306 DQE | [TI SCPS113O](https://www.ti.com/lit/ds/symlink/pca9306.pdf), p4 Table5-1; pp13–18, especially §8.1.7–8.1.8 and Fig9-1/9-2 | Physical8-pin map; EN/VREF2 common node through200k; separate bus pullups; explicit off clamp; LDO bias-backfeed concern |
| MAX98357A EWL | [ADI 19-6779 Rev13](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX98357A-MAX98357B.pdf), p7 DC; p15 pin description; p17 SD_MODE; p33 supply input | WLP nine bumps, threshold extrema, internal92..108k pulldown; local100nF+10uF bypass |
| IM69D130 | [Infineon v1.0, 2017-12-19](https://www.infineon.com/assets/row/public/documents/30/49/infineon-im69d130-datasheet-en.pdf), pp7–10 electrical/application; p12 Table7 | Physical five pads, 1.62..3.6V operating range,100nF bypass, stereo slots, 3.072MHz duty48..52%,13ns edge limit |
| SN74LVC1G07 DPW | [TI SCES296AG](https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf), pp3–6 pin/DC; DPW0005A drawing | New open-drain non-inverting EN clamp; 0.8x0.8mm body, 0.4mm max height,1NC/2A/3GND/4Y/5VCC |
| SN74LVC1G3157 DSF | [TI SCES424O](https://www.ti.com/lit/ds/symlink/sn74lvc1g3157.pdf), p3 Table4-1; pp6–8 DC; DSF0006A drawing | SD_MODE rail selector: physical6pins;1x1mm,0.35mm pitch,0.4mm max height;140ohm full-range RON and1uA on/off leakage bounds |

Retrieved PDF byte hashes are in `AUDIO_TRANSLATOR_SOURCE_MANIFEST.json` when the server allowed a direct download. A failed binary download is not substituted by a claimed local PDF; the linked primary document was read through the browsing tool.

## Implemented corrections

`audio_translator_corrections.py` runs after the recovered migration and asserts physical pin coverage. RJW is not interchangeable with PW/RHL; RSV is not interchangeable with PW/BQB. Both MAX98357A parts use A1=SD_MODE,A2=VDD,A3=OUTP,B1=DIN,B2=GAIN_SLOT,B3=OUTN,C1=BCLK,C2=GND,C3=LRCLK. GAIN_SLOT is tied to actual ground for12dB gain. Artificial `TIE_GND_*` labels are converted to GND and missing bottom terminals of R_LS1_A4/B4 are added. The original direction allocation remains: QSPI bank1 controlled byGPIO0; QSPI bank2 A→B; camera data/sync A→B, camera XCLK B→A; PDM/UART return A→B and host clocks/transmit B→A. Unused inputs are at defined levels and unused outputs are NC.

The camera PCA9306 now has a hard EN-low path. U8_CAM_ISO2 spare A4 senses its own CAM_DOVDD rail; B4 feeds a10k pulldown and U8_CAM_SCCB_EN powered by3V3_SYS. With camera VCCA below100mV, the AXC output is high impedance, the pull defines low, and the open-drain buffer clamps LS4_VREF2_EN. When camera power is present, the buffer releases the200k bias. VREF1=0 alone never justified the inherited isolation claim. A100k DOVDD bleed and a100k system-reference bleed give bias current a return path. The rail-sense channel high-level load is about0.33mA, below the AXC12mA3V test condition whose minimumVOH=2.3V exceeds the1G07 VIH=2V. AtOFF,10k times the sum of AXC Ioff2µA and buffer input leakage5µA gives≤70mV, below VIL0.8V. This is a source-derived DC bound; ramp transients still require bench testing.

MK2_C VDD and SELECT now use1V8_SYS, matching the microphones sharing the PDM bus, instead of the delayed FPGA IO rail. J_BRIDGE_IN P4/P5 must be routed locally to this rail; their old NC_TRUNK_PASS notes must be removed in both netlist and connector contract. This avoids a powered microphone driving an unpowered peer. Local100nF caps are explicit for all microphones. Firmware stops PDM_CLK low for sleep and waits up to50ms for the tight sensitivity startup specification.

The nRF GPIO specification VDD−0.4V cannot guarantee MAX98357A left-channel selection above B2max=1.5V. U10_SD_BUF is therefore an SN74LVC1G3157DSFR SPDT rail selector on the right:1B2=1V8_SYS,2GND,3B1=GND,4A=AMP_SD_MODE_1V8,5VCC=1V8_SYS,6S=local nRF request. A47k select pulldown defines resetOFF. S low connects the trunk to actualGND; S high connects it to1V8_SYS. Using the conservative140ohm full-signal-range switch bound at1.65V over−40..125C,35uA SD load and1.8V±2% rail gives≥1.7591V leftON. With69.8k±1% and internal92..108k, rightON is0.995933..1.119626V, between B1max0.825V and B2min1.245V. Two1uA switch-leakage contributions times140ohm give≤0.28mV localOFF, below B0min0.08V. The selector threshold is0.75VCC high/0.25VCC low; at1.764V, nRF guaranteesVOH≥1.364V>1.323V andVOL≤0.4V<0.441V. Thus the settledDC comparison closes both channel selection andOFF, without a CMOS-output VOL0.1V gap or additional cross-board contacts.

Translator bypasses and amplifier100nF+10uF pairs are actual two-terminal rows. I2S data/clock idle pulls are explicit. nRF stays the only I2S master and ESP32 stays the only PDM clock master. No RTL, PCF or testbench changes are needed for these corrections.

## Remaining checks and limits

- OE remains hardwiredGND for these dedicated channels. TI VCC<100mV isolation and input pulls define the settled power-off state; this does not constitute proof that all rail ramps are glitch-free at system level. Verify QSPI configuration, GPIO0 strapping and cameraOFF during brownout on hardware.
- Firmware must configure AMP_SD_REQ low before enabling I2S. The settledDC source calculation closes the generic buffer VOL gap using theSPDT. Verify physicalSD voltage and shutdown current, startup/brownout transitions, break-before-make effects and cross-board ground offset over temperature. Ground rise/noise between the right selector and left amplifier must keep totalSD_OFF below80mV; no bench or routed return-path proof is claimed.
- 1V8_SYS±2% is a design allocation. Converter tolerance, FPC drop, ripple and load transient must fit this limit at U10_SD_BUF and the audio blocks; the arithmetic is not a measurement.
- The long PDM bus still needs extracted RC/flight-time analysis and 48..52% duty/13ns-edge checks at every microphone. Existing assumed propagation-delay budgets are not verified hardware results.
- [Infineon's product page](https://www.infineon.com/part/IM69D130) currently marks the microphone not for new design. Retain the known prototype footprint; flag procurement and require a separately reviewed replacement before production.
- Logic/switch placement is TBD and passives require exact manufacturer part numbers, DC-bias checks and assembly qualification. Their0.001g/device and0.008g passive-cluster masses are estimates charged to the budget, not measured savings. NOT FOR FAB remains mandatory.
