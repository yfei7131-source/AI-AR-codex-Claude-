# fw_compat_report (tools/check_fw_compat.py R2)

repo: `<Codex交接包>/最小GPIO参考_勿作为完整源码`

## Required repo content
- MISSING `docs/FEATURES_F01_F22.md`
- ok `firmware/main/board.c`
- ok `firmware/main/board.h`
- MISSING `firmware/main/camera_adapter.c`
- MISSING `firmware/main/display_adapter.h`
- MISSING `firmware/main/ble_control.c`
- MISSING `protocols/DEVICE_MEDIA_V1.md`
- MISSING `protocols/events.schema.json`
- MISSING `mobile/lib`
- MISSING `mobile/ios/Runner/GlassesBleBridge.swift`

**Repo incomplete -> result below covers ONLY the files present. Do NOT freeze GPIO.**

## Inputs
- board.h sha256 `f373f76ca8f976b23a13f8daff71c548cf64e2b9cc8dbb6375a3fe40b573d25f`
- board.c sha256 `ae291d376f5563011171540c45187d7e90babdd72f79d840ca240740fdf81348`

## gl_board struct slots (18)
`name, configured, privacy_interlock_verified, button_gpio, xclk, sda, scl, d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], vsync, href, pclk`

## Profile `esp32_s3_eye_mb_v2.2`  (condition: `CONFIG_GL_BOARD_EYE_V22`)  <- CHECKED
- configured=true, privacy_interlock_verified=false
- **privacy_interlock_verified != true -> firmware refuses capture; needs H05 T11/T12 evidence + Codex profile (ICR-08/09)**

| fw field | fw gpio | expected hw net | hw net on that gpio | constraint | verdict |
|---|---|---|---|---|---|
| button_gpio | 0 | KEY_BOOT | KEY_BOOT | strap: boot mode (pull-up) | match |
| xclk | 15 | CAM_XCLK_R | CAM_XCLK_R |  | match |
| sda | 4 | CAM_SIOD | CAM_SIOD |  | match |
| scl | 5 | CAM_SIOC | CAM_SIOC |  | match |
| d[0] | 11 | CAM_Y2 | CAM_Y2 |  | match |
| d[1] | 9 | CAM_Y3 | CAM_Y3 |  | match |
| d[2] | 8 | CAM_Y4 | CAM_Y4 |  | match |
| d[3] | 10 | CAM_Y5 | CAM_Y5 |  | match |
| d[4] | 12 | CAM_Y6 | CAM_Y6 |  | match |
| d[5] | 18 | CAM_Y7 | CAM_Y7 |  | match |
| d[6] | 17 | CAM_Y8 | CAM_Y8 |  | match |
| d[7] | 16 | CAM_Y9 | CAM_Y9 |  | match |
| vsync | 6 | CAM_VSYNC | CAM_VSYNC |  | match |
| href | 7 | CAM_HREF | CAM_HREF |  | match |
| pclk | 13 | CAM_PCLK_R | CAM_PCLK_R |  | match |

### Hardware nets with NO field in this firmware profile (need ICR, not a pin conflict)
- GPIO1 VBAT_ADC
- GPIO2 MIC_SD
- GPIO3 CAM_PWR_EN
- GPIO14 DISP_RST
- GPIO21 DISP_CS
- GPIO38 DISP_D0
- GPIO39 DISP_D1
- GPIO40 DISP_D2
- GPIO41 MIC_SCK
- GPIO42 MIC_WS
- GPIO45 DISP_PWR_EN
- GPIO46 BT_AUD_EN
- GPIO47 DISP_CLK
- GPIO48 DISP_D3

## Profile `board_unconfigured`  (condition: `else(!(CONFIG_GL_BOARD_EYE_V22))`)
- configured=false, privacy_interlock_verified=false

## Other GPIO-like definitions under firmware/ (0, review manually)

## RESULT
conflicts=0 incomplete_items=3 exit=2 (pins match where defined; NOT freezable)
