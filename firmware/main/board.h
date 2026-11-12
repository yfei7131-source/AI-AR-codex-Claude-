#ifndef GL_BOARD_H
#define GL_BOARD_H
#include <stdbool.h>
typedef struct {
    const char *name;
    bool configured, privacy_interlock_verified;
    int button_gpio, xclk, sda, scl, d[8], vsync, href, pclk;
    /* -1 means absent. These metadata fields do not bind audio or display drivers. */
    int cam_pwr_en, vbat_adc, mic_sck, mic_ws, mic_sd;
    int audio_uart_tx, audio_uart_rx;
} gl_board;
const gl_board *gl_board_profile(void);
#endif
