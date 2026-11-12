#include "camera_power.h"
#include <stddef.h>
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static esp_err_t isolate(const gl_board *board) {
    const int pins[] = {board->xclk, board->sda, board->scl,
        board->d[0], board->d[1], board->d[2], board->d[3],
        board->d[4], board->d[5], board->d[6], board->d[7],
        board->vsync, board->href, board->pclk};
    esp_err_t first = ESP_OK;
    for (size_t i = 0; i < sizeof(pins) / sizeof(pins[0]); i++) {
        if (pins[i] < 0) continue;
        esp_err_t result = gpio_reset_pin(pins[i]);
        if (first == ESP_OK) first = result;
        result = gpio_set_direction(pins[i], GPIO_MODE_INPUT);
        if (first == ESP_OK) first = result;
        result = gpio_set_pull_mode(pins[i], GPIO_FLOATING);
        if (first == ESP_OK) first = result;
    }
    return first;
}

static esp_err_t supply(const gl_board *board, bool on) {
    if (!board || !board->configured) return ESP_ERR_INVALID_STATE;
    if (board->cam_pwr_en < 0) return ESP_OK;
    esp_err_t isolated = isolate(board);
    /* Attempt OFF even if one signal failed to isolate. Never attempt ON then. */
    esp_err_t result = gpio_set_level(board->cam_pwr_en, on && isolated == ESP_OK);
    if (result != ESP_OK) return result;
    result = gpio_set_direction(board->cam_pwr_en, GPIO_MODE_OUTPUT);
    if (result != ESP_OK) return result;
    return isolated;
}

esp_err_t gl_camera_power_off(const gl_board *board) {
    return supply(board, false);
}

esp_err_t gl_camera_power_on(const gl_board *board) {
    if (!board || !board->privacy_interlock_verified) return ESP_ERR_NOT_SUPPORTED;
    esp_err_t result = supply(board, true);
    if (result == ESP_OK && board->cam_pwr_en >= 0) {
        /* Bring-up target only. Final delay and rail order require the chosen sensor. */
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    return result;
}
