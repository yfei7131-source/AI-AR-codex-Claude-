#include "sdkconfig.h"
#include "board.h"
/* Reference only: Espressif ESP32-S3-EYE-MB V2.2 schematic sheets 3/4.
 * https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-EYE-MB_20211201_V2.2.pdf
 * Stock GPIO3 power LED is NOT a camera-linked privacy indicator.
 * No profile in this release allows physical camera acquisition.
 */
const gl_board *gl_board_profile(void) {
#if CONFIG_GL_BOARD_EYE_V22
    static const gl_board board={"esp32_s3_eye_mb_v2.2",true,false,0,15,4,5,{11,9,8,10,12,18,17,16},6,7,13};
#elif CONFIG_GL_BOARD_S3_CARRIER_A
    /* J4 breakout follows the EYE data-bit order. BOOT is active low.
     * The downstream power lamp alone does not establish fail-safe privacy. */
    static const gl_board board={"devkitc_v1.1_s3_carrier_a",true,false,0,15,4,5,{11,9,8,10,12,18,17,16},6,7,13};
#else
    static const gl_board board={"board_unconfigured",false,false,-1,-1,-1,-1,{-1,-1,-1,-1,-1,-1,-1,-1},-1,-1,-1};
#endif
    return &board;
}
