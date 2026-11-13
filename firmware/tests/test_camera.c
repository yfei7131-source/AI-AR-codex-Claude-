/* Execute the production camera adapter with deterministic IDF fault injection. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "camera_adapter.h"
#include "camera_power.h"
#include "esp_camera.h"
#include "driver/gpio.h"

static gl_board board;
static unsigned operations, resets, init_calls, deinit_calls, unlock_calls, consumed;
static bool locked, authorized, no_frame;
static int rail, fail_pin;
static esp_err_t init_result;
static size_t psram;
static uint8_t jpeg[] = {0xff,0xd8,0xff,0xd9};
static camera_fb_t frame = {PIXFORMAT_JPEG, sizeof(jpeg), jpeg};

esp_err_t gpio_reset_pin(int pin) {
    operations++; resets++;
    return pin == fail_pin ? ESP_FAIL : ESP_OK;
}
esp_err_t gpio_set_direction(int pin, int mode) {
    operations++;
    assert((pin == 3 && mode == GPIO_MODE_OUTPUT) || (pin != 3 && mode == GPIO_MODE_INPUT));
    return ESP_OK;
}
esp_err_t gpio_set_pull_mode(int pin, int mode) {
    operations++; assert(pin != 3 && mode == GPIO_FLOATING); return ESP_OK;
}
esp_err_t gpio_set_level(int pin, unsigned level) {
    operations++; assert(pin == 3 && level <= 1); rail = (int)level; return ESP_OK;
}
void vTaskDelay(unsigned ticks) {
    assert(locked && rail == 1 && ticks >= 10);
}
size_t heap_caps_get_total_size(unsigned caps) { (void)caps; return psram; }
esp_err_t esp_camera_init(const camera_config_t *config) {
    init_calls++; assert(locked && rail == 1 && resets == 14);
    assert(config->pin_xclk == 15 && config->pin_d0 == 11 && config->pin_d7 == 16);
    return init_result;
}
esp_err_t esp_camera_deinit(void) {
    deinit_calls++; assert(rail == 1 || init_calls == 0); return ESP_OK;
}
camera_fb_t *esp_camera_fb_get(void) { return no_frame ? NULL : &frame; }
void esp_camera_fb_return(camera_fb_t *returned) { assert(returned == &frame); }
static bool authorize(void *context) {
    (void)context; locked = authorized; return authorized;
}
static void unlock(void *context) { (void)context; assert(locked); locked = false; unlock_calls++; }
static bool consume(const uint8_t *data, size_t count, void *context) {
    (void)context; assert(data == jpeg && count == sizeof(jpeg) && rail == 1);
    consumed++; return true;
}
static const gl_capture_gate gate = {authorize, unlock, NULL, consume};
static void setup(void) {
    board = (gl_board){.name="injected_test_board", .configured=true, .privacy_interlock_verified=true,
        .button_gpio=0, .xclk=15, .sda=4, .scl=5, .d={11,9,8,10,12,18,17,16},
        .vsync=6, .href=7, .pclk=13, .cam_pwr_en=3};
    operations=resets=init_calls=deinit_calls=unlock_calls=consumed=0;
    rail=0; fail_pin=-1; locked=no_frame=false; authorized=true; init_result=ESP_OK; psram=1024;
    frame.format=PIXFORMAT_JPEG;
}
static void finished(void) {
    assert(rail == 0 && !locked && unlock_calls == 1 && deinit_calls == 1);
    assert(resets == 28);
}
int main(void) {
    size_t bytes=99;
    setup(); board.privacy_interlock_verified=false;
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_ERR_NOT_SUPPORTED && bytes==0 && operations==0);
    assert(gl_camera_power_on(&board)==ESP_ERR_NOT_SUPPORTED && operations==0);
    puts("PASS unverified_board_never_energizes_camera");
    setup(); assert(gl_camera_power_off(&board)==ESP_OK && rail==0 && resets==14);
    puts("PASS boot_isolates_all_signals_and_holds_external_rail_off");
    setup(); authorized=false;
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_ERR_INVALID_STATE && operations==0 && init_calls==0);
    puts("PASS stale_authorization_does_not_power_on");
    setup(); psram=0;
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_ERR_NO_MEM && operations==0);
    puts("PASS missing_psram_does_not_power_on");
    setup();
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_OK && bytes==4 && consumed==1); finished();
    puts("PASS valid_frame_stops_camera_then_isolates_and_powers_off");
    setup(); init_result=ESP_FAIL;
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_FAIL && bytes==0 && consumed==0); finished();
    puts("PASS_partial_initialization_failure_cleans_clock_and_rails");
    setup(); no_frame=true;
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_FAIL && consumed==0); finished();
    puts("PASS framebuffer_failure_cleans_clock_and_rails");
    setup(); frame.format=0;
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_FAIL && bytes==0 && consumed==0); finished();
    puts("PASS invalid_frame_cleans_clock_and_rails");
    setup(); fail_pin=15;
    assert(gl_camera_capture(&board,&bytes,&gate)==ESP_FAIL && rail==0 && init_calls==0 && !locked);
    puts("PASS isolation_failure_keeps_camera_rail_off");
    puts("9/9 camera lifecycle fault-injection checks passed (IDF stubs, no hardware)");
    return 0;
}
