#ifndef GL_CORE_H
#define GL_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define GL_CONTROL_SIZE 8u
#define GL_STATUS_SIZE 20u
#define GL_LOG_CAPACITY 16u
enum gl_opcode { GL_STATUS=1, GL_CAPTURE=2, GL_CANCEL=3, GL_CONSENT=4, GL_CLEAR_LOG=5 };
enum gl_state { GL_IDLE=0, GL_CAPTURING=1, GL_ERROR=2 };
enum gl_error { GL_OK=0, GL_BAD_FRAME=1, GL_BOARD_MISSING=2, GL_PRIVACY_UNVERIFIED=3,
    GL_NOT_CONNECTED=4, GL_NO_CONSENT=5, GL_BUSY=6, GL_CAMERA_FAILED=7,
    GL_MEDIA_NOT_CONFIGURED=8, GL_DUPLICATE=9, GL_QUEUE_FULL=10, GL_STALE_EVENT=11 };
typedef struct { uint8_t opcode; uint16_t request_id; uint32_t argument; } gl_command;
typedef struct { uint32_t uptime_ms; uint16_t request_id; uint8_t code; } gl_error_record;
typedef struct {
    bool board_ready, privacy_verified, connected, consent, capture_requested;
    bool has_last_request;
    uint8_t state, last_error;
    uint16_t request_id, last_request_id;
    uint16_t recent_ids[GL_LOG_CAPACITY];
    size_t recent_head, recent_count;
    uint32_t captures, errors, epoch;
    gl_error_record log[GL_LOG_CAPACITY];
    size_t log_head, log_count;
} gl_device;

bool gl_decode_command(const uint8_t *bytes, size_t length, gl_command *out);
void gl_init(gl_device *device, bool board_ready, bool privacy_verified);
void gl_connected(gl_device *device, bool connected);
uint8_t gl_capture_allowed(const gl_device *device);
uint8_t gl_apply(gl_device *device, const gl_command *command, uint32_t now_ms);
uint8_t gl_apply_at_epoch(gl_device *device, const gl_command *command, uint32_t epoch, uint32_t now_ms);
uint8_t gl_button(gl_device *device, bool long_press, uint32_t now_ms);
void gl_capture_finished(gl_device *device, bool success, uint32_t now_ms);
void gl_capture_finished_with_media(gl_device *device,bool success,bool media_available,uint32_t now_ms);
void gl_error_push(gl_device *device, uint8_t code, uint32_t now_ms);
bool gl_error_get(const gl_device *device, size_t index, gl_error_record *out);
void gl_encode_status(const gl_device *device, uint32_t now_ms, uint8_t out[GL_STATUS_SIZE]);
#endif
