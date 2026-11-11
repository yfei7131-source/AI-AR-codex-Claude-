#ifndef GL_RUNTIME_H
#define GL_RUNTIME_H
#include "core.h"
#include "media_core.h"
#include "esp_err.h"
enum gl_event_kind { GL_EVENT_COMMAND, GL_EVENT_CONNECTED, GL_EVENT_BUTTON, GL_EVENT_PAIR, GL_EVENT_SESSION };
typedef struct { enum gl_event_kind kind; gl_command command; bool value; uint32_t epoch; gl_session_command session; } gl_event;
bool gl_post_event(const gl_event *event);
void gl_status_snapshot(uint8_t out[GL_STATUS_SIZE]);
esp_err_t gl_ble_start(void);
void gl_ble_notify(void);
void gl_button_start(void);
#endif
