#include "runtime.h"
#include "board.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
static void button_task(void *arg) {
    int pin=(int)(intptr_t)arg;
    unsigned stable=0; bool pressed=false, long_sent=false, pair_sent=false;
    for (;;) {
        bool low=gpio_get_level(pin)==0;
        if (low) {
            if (stable<1000) stable++;
            if (stable>=3) pressed=true; /* 30ms debounce */
            if (stable>=100 && !long_sent) {
                gl_event event={.kind=GL_EVENT_BUTTON,.value=true}; gl_post_event(&event); long_sent=true;
            }
            if (stable>=300 && !pair_sent) {
                gl_event event={.kind=GL_EVENT_PAIR};gl_post_event(&event);pair_sent=true;
            }
        } else {
            if (pressed && !long_sent) { gl_event event={.kind=GL_EVENT_BUTTON,.value=false}; gl_post_event(&event); }
            stable=0; pressed=false; long_sent=false;pair_sent=false;
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
void gl_button_start(void) {
    const gl_board *b=gl_board_profile();
    if (!b->configured || b->button_gpio<0) return;
    gpio_config_t c={.pin_bit_mask=1ULL<<b->button_gpio,.mode=GPIO_MODE_INPUT,.pull_up_en=GPIO_PULLUP_ENABLE};
    if (gpio_config(&c)==ESP_OK) xTaskCreate(button_task,"gl_button",2048,(void *)(intptr_t)b->button_gpio,3,NULL);
}
