# Explicit privacy analog circuit — NOT FOR FAB

2026-11-17 primary-source review exposed inherited symbolic-only amplifier/comparator ports. `privacy_corrections.py` expands these into physical pins without changing the FPGA or the inherited interlock net names.

[TI INA185 SBOS378A](https://www.ti.com/lit/ds/symlink/ina185.pdf), Table4-1 p3 and §7.1.1/§7.4: the **DRL** six-pin variant has OUT1, GND2, IN+3, IN−4, REF5 and VS6. Grounding REF gives unidirectional positive-current sensing. The migration connects VS to3V3_SYS, IN+ toLED_2V8 and IN− toISENSE_N, and adds100nF across VS/GND. The sense resistor retains Kelvin layout requirements. No DCK variant pin numbers are substituted.

[TI TLV7042 SLVSE13J](https://www.ti.com/lit/ds/symlink/tlv7042.pdf), Table4-2 and DSG Fig4-6 p4: OUTA1, INA−2, INA+3, VEE4, INB+5, INB−6, OUTB7, VCC8; EP goes to VEE. Both open-drain outputs share PRIV_WINDOW_OK. ChannelA compares sense(+) to lower threshold(−); channelB compares upper threshold(+) to sense(−). Thus either out-of-window condition pulls the interlock low. VCC=3V3_SYS, VEE/EP=GND and local100nF supply bypass are explicit.

The inherited divider becomes three actual two-terminal resistors:3V3_SYS→33.2k→PRIV_VTH_H→32.4k→PRIV_VTH_L→32.4k→GND. At3.3V its nominal thresholds are2.18204V and1.09102V. R_PRIV_PU10k remains connected to **V_INA_OUT**, so absent LED current cannot be replaced with a permanently high3.3V pullup.

The formerly unspecified filter is now R_PRIV_RC1k and C_PRIV_RC1uF. The local discharge time constant is1ms; the nominal pullup-charge time constant is11ms after including the10k dynamic pullup. These are schematic calculations, not measured turn-on/off times. Capacitor bias/tolerance, comparator output resistance, amplifier output swing, LDO EN current, threshold tolerances, supply ramps, LED open/short faults and actual sensor timing still require bench validation. The full interlock remains NOT FOR FAB.
