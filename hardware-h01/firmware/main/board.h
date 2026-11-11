#ifndef GL_BOARD_H
#define GL_BOARD_H
#include <stdbool.h>
typedef struct {
    const char *name;
    bool configured, privacy_interlock_verified;
    int button_gpio, xclk, sda, scl, d[8], vsync, href, pclk;
} gl_board;
const gl_board *gl_board_profile(void);
#endif
