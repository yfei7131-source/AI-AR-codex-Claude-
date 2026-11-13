#ifndef TEST_GPIO_H
#define TEST_GPIO_H
#include "esp_err.h"
#define GPIO_MODE_INPUT 1
#define GPIO_MODE_OUTPUT 2
#define GPIO_FLOATING 0
esp_err_t gpio_reset_pin(int pin);
esp_err_t gpio_set_direction(int pin, int mode);
esp_err_t gpio_set_pull_mode(int pin, int mode);
esp_err_t gpio_set_level(int pin, unsigned level);
#endif
