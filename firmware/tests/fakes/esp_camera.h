#ifndef TEST_ESP_CAMERA_H
#define TEST_ESP_CAMERA_H
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#define PIXFORMAT_JPEG 1
#define FRAMESIZE_VGA 1
#define LEDC_TIMER_0 0
#define LEDC_CHANNEL_0 0
#define CAMERA_FB_IN_PSRAM 1
#define CAMERA_GRAB_WHEN_EMPTY 1
typedef struct {
    int pin_pwdn, pin_reset, pin_xclk, pin_sccb_sda, pin_sccb_scl;
    int pin_d0, pin_d1, pin_d2, pin_d3, pin_d4, pin_d5, pin_d6, pin_d7;
    int pin_vsync, pin_href, pin_pclk, xclk_freq_hz, ledc_timer, ledc_channel;
    int pixel_format, frame_size, jpeg_quality, fb_count, fb_location, grab_mode;
} camera_config_t;
typedef struct { int format; size_t len; uint8_t *buf; } camera_fb_t;
esp_err_t esp_camera_init(const camera_config_t *config);
esp_err_t esp_camera_deinit(void);
camera_fb_t *esp_camera_fb_get(void);
void esp_camera_fb_return(camera_fb_t *frame);
#endif
