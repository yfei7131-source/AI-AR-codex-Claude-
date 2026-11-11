#include "camera_adapter.h"
#include "esp_camera.h"
#include "esp_heap_caps.h"
esp_err_t gl_camera_capture(const gl_board *b, size_t *frame_bytes, const gl_capture_gate *gate) {
    if (!b || !frame_bytes || !b->configured || !b->privacy_interlock_verified) return ESP_ERR_NOT_SUPPORTED;
    *frame_bytes=0;
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
        esp_err_t result=esp_camera_init(&c);
        gate->unlock(gate->context);
        if (result!=ESP_OK) return result;
    }
    camera_fb_t *fb=esp_camera_fb_get();
    if (!fb) { esp_camera_deinit(); return ESP_FAIL; }
    bool valid=fb->format==PIXFORMAT_JPEG && fb->len>=4 && fb->buf[0]==0xff && fb->buf[1]==0xd8;
    if (valid) {
        *frame_bytes=fb->len;
        if(gate->consume_frame) gate->consume_frame(fb->buf,fb->len,gate->context);
    }
    /* Consumer may retain a bounded RAM copy; camera framebuffer itself is always returned. */
    esp_camera_fb_return(fb);
    esp_camera_deinit(); /* stop capture clock/tasks between explicitly requested frames */
    return valid ? ESP_OK : ESP_FAIL;
}
