#ifndef GL_MEDIA_SERVICE_H
#define GL_MEDIA_SERVICE_H
#include "media_core.h"
#include "esp_err.h"
void gl_media_service_init(void);
void gl_media_service_pair_window(void);
void gl_media_service_revoke(void);
void gl_media_service_tick(void);
void gl_media_service_command(const gl_session_command *command,bool connected);
size_t gl_media_service_session(char *out,size_t capacity);
bool gl_media_service_publish(const uint8_t *jpeg,size_t length,uint16_t request_id,bool reviewed);
#endif
