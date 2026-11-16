# Rev D1 power source review — NOT FOR FAB

Reviewed 2026-11-17. This is a static engineering correction, not a measured prototype.
The migration records physical pins, two-terminal capacitors and discrete load isolation in the NETLIST/BOM.

| Evidence | Primary source | Checked locations | Engineering result |
|---|---|---|---|
| PWR-01 | [TI BQ25180 SLUSE99C](https://www.ti.com/lit/ds/symlink/bq25180.pdf) | Table6-1 pp4; electrical/TS pp5-10; registers pp31-39; application pp41-42 | Eight balls verified. Independent IN/SYS/BAT bypass capacitors added. 50mA profile is only a candidate for the110mAh pack; TS and watchdog remain enabled. |
| PWR-02 | [TI BQ25180 Japanese translation](https://www.ti.com/jp/lit/ds/symlink/bq25180.pdf?ts=1780927368744) | p52 drawing4229296/A YBG0008-C01 | 0.4mm pitch; max1.610x1.060x0.5mm envelope. The English download's present appended pages omit this outline; the official translated drawing supplies it. |
| PWR-03 | [TI BQ25170 SLUSDJ8A](https://www.ti.com/lit/ds/symlink/bq25170.pdf) | Table5-1 p3; §7.3.1 pp14-16 | Pin5 is STAT and pin6 is /PG: corrected the interrupted migration's reversal. RISET5.49k gives54.64mA nominal, approximately48.69..60.72mA from KISET270..330AΩ and1% resistor. VSET27k selects4.20V. Required IN/OUT capacitors and ground EP explicit. |
| PWR-04 | [TI TPS63805 SLVSDS9E](https://www.ti.com/lit/ds/symlink/tps63805.pdf) | Table7-1 p3; §8.3 p4; §10.2 pp15-19; YFF0015 drawingp39 | All15balls mapped; switch-node inductor and feedback explicit. CIN10uF/COUT22uF are nominal design values; qualification must retain4uF/7uF effective capacitance. YFF maxheight0.625mm replaces0.5mm. |
| PWR-05 | [TI TPS62840 SLVSEC6D](https://www.ti.com/lit/ds/symlink/tps62840.pdf) | Pin tablepp4-5; Table1 p13; Table3 p17; DLC0008B p36 | All8DLC pins verified. For TPS62840DLC1.8V, VSET goes to GND via0Ω. MODE/STOP go GND; EN to VSYS.2.2uH/10uF filter explicit; DLC envelope1.5x2.0mm nominal and1mm maxheight. |
| PWR-06 | [TI LM66200 SLVSG04](https://www.ti.com/lit/ds/symlink/lm66200.pdf) | Table5-1 p3; §9 p13 | All8pins mapped, both GND and both VOUT pins included, /ON tied GND. RON corrected22→40mΩ typical. Automatic selection alone does not guarantee right-pack load isolation while charging. |
| PWR-07 | [Nexperia PMV65XP](https://assets.nexperia.com/documents/data-sheet/PMV65XP.pdf) | Pin tablep2; electrical pp5-6 | Q_CHG_ISO_R gate1/source2/drain3; source=right pack, drain=OR VIN2.100Ω gate feed from VBUS and100k gate pulldown. Off during5V cable charging. Its diode orientation blocks right-pack discharge while off; LM66200 supplies reverse blocking. |
| PWR-08 | [Nexperia 2N7002](https://assets.nexperia.com/documents/data-sheet/2N7002.pdf) | Pin tablep1; electricalp5 | Q_CHG_MUTE_R gate1/source2/drain3 clamps right SD_MODE to GND during5V cable charging. The existing69.8k resistor limits current from nRF GPIO. Right audio is deliberately muted with USB attached. |

All new capacitor and resistor entries include both electrical terminals. Exact MLCC MPNs, bias curves and layout remain open; the values and envelopes are procurement constraints rather than claims of stocked or installed parts. BOM-59 is superseded to prevent double counting its charger-capacitor lump. Masses assigned to new peripherals are engineering estimates.

The compact TPS638050.47uH inductor is still unqualified. Its effective inductance must remain0.37..0.57uH under actual load and temperature. The recovered claim that4.5A saturation current exceeds the switch limit was false: the boost maximum limit is5.75A. An unchanged tiny area allowance is not evidence that an adequate inductor fits.

Required pack boundary: independently protected1S P+/P- plus cell-mounted10kNTC and return. Raw Grepow catalog cells do not establish PCM, current ratings or the final pack pin order. No internal protector threshold or unprovided battery specification has been invented. Charge/discharge current limits, OVP/UVP/short-circuit protection, NTC curve, pack dimensions and mass need vendor qualification. GRP22055047mAh cannot inherit the110mAh charge profile.

`CHARGER_CONFIGURATION_REV_D1.json` records candidate bring-up settings. BQ25180 defaults permit10mA charging with a nominal60°C hot threshold before host setup or after watchdog reset. A programmed45°C threshold does not create a hardware45°C power-on guarantee. This default-state safety review remains a fabrication blocker.

Load isolation and amplifier mute close the identified5V static wiring path, but low-VBUS transition behavior, USB inrush, hot-plug, thermal behavior and right charge termination must be measured. Charge approval remains OPEN. No EVT board, native CAD ERC/DRC or real cell test was executed by this helper.
