# Rev D1 SoC source review — NOT FOR FAB

Reviewed 2026-11-17. `soc_corrections.py` changes CSV engineering data; it is not native CAD or hardware validation.

Sources:

- Nordic [nRF5340 WLCSP pin table3](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/pin.html): all95physical balls, supply grounds and PSEL GPIO assignments. CMAA and CLAA pin assignments match, but package footprint must use CMAA drawing.
- Nordic [reference circuits, CMAA Config3/Table25](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/ref_circuitry.html) and [official reference-layout ZIP1.3](https://nsscprodmedia.blob.core.windows.net/prod/software-and-other-downloads/reference-layouts/nrf5340/nrf5340-xxaa-reference-layout-1_3.zip), member `nRF5340-CMAA Reference Layout 1_0/Schematic and Layout pdf files/nrf5340_cmaa_config3_schematic.pdf`. Downloaded exact member via HTTP Range and ZIP decompression; PDF SHA256 `efd696d6f662552371c27ef80dd3a8527e8f1c066ddee42a11c210144b5bf6ba`. Source schematic dated2025-02-20. C1..C14/L1..L4 retained with `NRF_` prefix.
- Nordic [normal voltage regulator configuration](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/regulators.html): VDDH must tie VDD; both VREGMAIN/VREGRADIO reset in LDO mode. The populated10uH inductors permit enabling `VREGMAIN.DCDCEN=1` and `VREGRADIO.DCDCEN=1`. Do not enable VREGH DC/DC; DCCH isNC.
- Nordic [HFXO requirements and internal capacitor setup](https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/chapters/oscillators/doc/oscillators.html): use32MHz ATcut parallel crystal; CL6..12pF; BLE packets>200bytes require total±30ppm. Internal capacitor trim must be computed from per-chipFICR before HFXO start. LFRC must be calibrated; no32.768kHzcrystal is fitted.
- Espressif [ESP32-S3-PICO-1 datasheetv1.2](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.pdf), pp11–16,29–30: physical pins1..57, SiP3.0..3.6V, ≥500mA supply capability, pin4CHIP_PU10k/1uF RC, externalbulk22uF. An additional1uF VDD_SPIdecoupler is a designallowance, not a claimedtypicalschematicvalue. Pin29 isoutput memory supply, removed fromgeneric3V3inputbundle. GPIO46 isI/O inthisS3datasheet; do not confuse ESP32-S2 input-onlyGPIO46. In-package40MHzcrystal/RFmatch are retained; only antenna tuning pads external.
- TDK [DS-000347 ICM-42688-P v1.6](https://product.tdk.com/system/files/dam/doc/product/sensor/mortion-inertial/imu/data_sheet/ds-000347-icm-42688-p-v1.6.pdf), sec4.1/4.2,14.48/15.18: pin9FSYNC,5VDDIO,8VDD,7reservedGND;0.1uF+2.2uF VDD/10nFVDDIO. OfficialTDK product page lists1.9; inspected primary indexedv1.6pin/FSYNCtables. The directPDFdownload failed/timeouts inthissession; no unverified claim of1.9review ismade.
- Epson [FA-128 package/specification](https://download.epsondevice.com/td/pdf/brief/FA-128_en.pdf), p1, and [EpsonChina indexed catalog](https://www.epson.com.cn/ed/search/prod-search.html): candidateQ22FA12800025,32MHz8pF±10ppm initial/±10ppm−20..75°C, ESR≤60Ω. Pins1/3crystal and2/4caseGND. Currentbrief ordering format changed; finalcontrolledvendororderingsuffix remainsOPEN. Candidate is not procurement released.

Changes beyond recovered Claude script:

- DECRF and DECR tied per actual Nordic schematic, instead of independent virtual decoupling ports. DECN100nF, DECA1uF, DECD1uF, radio1uF+2.2nF, explicit2x10uH DC/DC inductors. VBUSground and DECUSBNC follow noUSBconfig3; six separate genericDEC capacitors were incorrect.
- Two2.2nH seriesRF inductors and0.7pFshunt are reference values; antenna-dependent tuning capacitor isDNP. VNA/OTA tuning and enclosure detuning remainOPEN. A 50Ωfeed does not imply the nakedANTball is50Ω.
- SWD fivephysicalpads now explicit. nRESET uses siliconpull-up; no virtualpadpretending resistor.
- CompleteESP CHIP_PUcapreturn; separateVDD_SPIoutput from3V3_SYS; deterministicbootstraps; all57pins handled. GPIO33..37remainunused, GPIO26/SPICS1PSRAMreserved.
- MoveIMUVDD/VDDIO/AP_CS to1V8_SYS, matching I2Cpull-ups. Pin9staysFSYNC fromFPGA; firmware selectsFSYNC before anyINT2routing, setsfallingedge, and leavesexternalpull-upsabsent toavoidunpoweredFPGAbackfeed. These sequencing obligations require benchvalidation.

Open gates: exactcrystalcontrolledorderingcode andloadtrim; passiveprocurementMPNs/effectivecapacitance; nRFfirmwarebuild/programming/BTaudio andLFRCcalibration; RF/VNA/OTA; allPCBlayout/DRC/mechanics; realpower/temperature/mass. Componentmasses inCSV remain estimates. No fabricatedsilicon or prototypes were tested.
