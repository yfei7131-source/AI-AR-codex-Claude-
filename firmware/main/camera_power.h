#ifndef GL_CAMERA_POWER_H
#define GL_CAMERA_POWER_H
#include "board.h"
#include "esp_err.h"

/* Both functions isolate SCCB, DVP and XCLK before changing the external rail.
 * They are only active on boards with a dedicated cam_pwr_en pin. */
esp_err_t gl_camera_power_off(const gl_board *board);
esp_err_t gl_camera_power_on(const gl_board *board);
#endif
