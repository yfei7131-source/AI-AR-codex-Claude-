#include "camera_adapter.h"
#include "camera_power.h"
#include "esp_camera.h"
#include "esp_heap_caps.h"
esp_err_t gl_camera_capture(const gl_board *b, size_t *frame_bytes, const gl_capture_gate *gate) {
    if (!frame_bytes) return ESP_ERR_INVALID_ARG;
    *frame_bytes=0;
    if (!b || !b->configured || !b->privacy_interlock_verified) return ESP_ERR_NOT_SUPPORTED;
    if (!gate || !gate->lock_and_authorize || !gate->unlock) return ESP_ERR_INVALID_STATE;
    if (!heap_caps_get_total_size(MALLOC_CAP_SPIRAM)) return ESP_ERR_NO_MEM;
    {
        camera_config_t c={0};
        c.pin_pwdn=-1; c.pin_reset=-1; c.pin_xclk=b->xclk;
        c.pin_sccb_sda=b->sda; c.pin_sccb_scl=b->scl;
        c.pin_d0=b->d[0]; c.pin_d1=b->d[1]; c.pin_d2=b->d[2]; c.pin_d3=b->d[3];
        c.pin_d4=b->d[4]; c.pin_d5=b->d[5]; c.pin_d6=b->d[6]; c.pin_d7=b->d[7];
        c.pin_vsync=b->vsync; c.pin_href=b->href; c.pin_pclk=b->pclk;
        c.xclk_freq_hz=16000000; c.ledc_timer=LEDC_TIMER_0; c.ledc_channel=LEDC_CHANNEL_0;
        c.pixel_format=PIXFORMAT_JPEG; c.frame_size=FRAMESIZE_VGA; c.jpeg_quality=12;
        c.fb_count=1; c.fb_location=CAMERA_FB_IN_PSRAM; c.grab_mode=CAMERA_GRAB_WHEN_EMPTY;
        /* Serialize authorization with camera initialization, closing the check/start race. */
        if (!gate->lock_and_authorize(gate->context)) return ESP_ERR_INVALID_STATE;
        esp_err_t result=gl_camera_power_on(b);
        if (result==ESP_OK) result=esp_camera_init(&c);
        if (result!=ESP_OK) {
            /* Init may have partially attached clocks/SCCB before returning an error. */
            esp_camera_deinit();
            gl_camera_power_off(b);
        }
        gate->unlock(gate->context);
        if (result!=ESP_OK) return result;
    }
    camera_fb_t *fb=esp_camera_fb_get();
    if (!fb) { esp_camera_deinit(); gl_camera_power_off(b); return ESP_FAIL; }
    bool valid=fb->format==PIXFORMAT_JPEG && fb->len>=4 && fb->buf[0]==0xff && fb->buf[1]==0xd8;
    if (valid) {
        *frame_bytes=fb->len;
        if(gate->consume_frame) gate->consume_frame(fb->buf,fb->len,gate->context);
    }
    /* Consumer may retain a bounded RAM copy; camera framebuffer itself is always returned. */
    esp_camera_fb_return(fb);
    esp_err_t stopped=esp_camera_deinit();
    esp_err_t powered_off=gl_camera_power_off(b);
    if (stopped!=ESP_OK) return stopped;
    if (powered_off!=ESP_OK) return powered_off;
    return valid ? ESP_OK : ESP_FAIL;
}
