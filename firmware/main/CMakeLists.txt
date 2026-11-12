idf_component_register(SRCS "main.c" "camera_adapter.c" "camera_power.c" "ble_control.c" "board.c" "button.c" "core.c" "display_adapter.c" "media_core.c" "media_service.c"
    INCLUDE_DIRS "." REQUIRES bt nvs_flash esp_driver_gpio esp_timer esp_driver_ledc esp32-camera esp_http_server esp_wifi esp_netif esp_event mbedtls)
