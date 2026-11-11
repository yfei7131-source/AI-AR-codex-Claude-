#ifndef GL_MEDIA_CORE_H
#define GL_MEDIA_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define GL_MEDIA_TOKEN_LENGTH 64u
#define GL_MEDIA_MAX_BYTES (2u*1024u*1024u)
#define GL_MEDIA_MAX_CHUNK 16384u
#define GL_MEDIA_FRAME_TTL 15000u
#define GL_MEDIA_MAX_TTL 120000u
typedef struct { uint8_t opcode; uint16_t request_id; uint32_t ttl_ms; } gl_session_command;
typedef struct {
    bool active;
    char token[65], sha256[65];
    uint8_t *buffer;
    size_t capacity, length;
    uint32_t expires_at, frame_expires_at, frame_id, next_frame_id, epoch;
    uint16_t capture_request_id, session_request_id;
} gl_media_store;
bool gl_session_decode(const uint8_t *bytes,size_t length,gl_session_command *out);
size_t gl_session_error_json(char *out,size_t capacity,uint16_t request_id,const char *error);
size_t gl_session_ready_json(char *out,size_t capacity,uint16_t request_id,const char *ssid,
                             const char *passphrase,const char *token,uint32_t remaining_ms);
void gl_media_init(gl_media_store *store);
void gl_media_clear_frame(gl_media_store *store);
void gl_media_revoke(gl_media_store *store);
bool gl_media_open(gl_media_store *store,const char *token,uint32_t ttl_ms,uint32_t now_ms);
void gl_media_tick(gl_media_store *store,uint32_t now_ms);
bool gl_media_authorized(gl_media_store *store,const char *authorization,uint32_t now_ms);
bool gl_media_publish(gl_media_store *store,uint8_t *storage,size_t capacity,const uint8_t *jpeg,size_t length,
                      const char *sha256,uint16_t capture_request_id,bool reviewed_capture,uint32_t now_ms);
bool gl_media_frame_id(const char *uri,uint32_t *id);
bool gl_media_range(const char *header,size_t total,size_t *offset,size_t *length);
int gl_media_copy(gl_media_store *store,const char *authorization,uint32_t id,const char *range,
                  uint32_t now_ms,uint8_t *out,size_t capacity,size_t *offset,size_t *copied);
#endif
