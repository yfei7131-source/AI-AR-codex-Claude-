#ifndef GL_CAMERA_ADAPTER_H
#define GL_CAMERA_ADAPTER_H
#include <stddef.h>
#include <stdint.h>
#include "board.h"
#include "esp_err.h"
typedef struct {
    bool (*lock_and_authorize)(void *context); /* true returns with authorization lock held */
    void (*unlock)(void *context);
    void *context;
    bool (*consume_frame)(const uint8_t *jpeg,size_t length,void *context);
} gl_capture_gate;
esp_err_t gl_camera_capture(const gl_board *board, size_t *frame_bytes, const gl_capture_gate *gate);
#endif
