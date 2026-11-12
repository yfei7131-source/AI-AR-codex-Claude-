#include "runtime.h"
#include "board.h"
#include "camera_adapter.h"
#include "camera_power.h"
#include "display_adapter.h"
#include "media_service.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
static gl_device device;
static QueueHandle_t events;
static SemaphoreHandle_t state_lock;
static const gl_display_adapter display={0}; /* Separate AR driver must be reviewed before binding. */
static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time()/1000); }
typedef struct { uint32_t epoch;uint16_t request_id;bool published; } capture_context;
bool gl_post_event(const gl_event *event) {
    if (!events) return false;
    xSemaphoreTake(state_lock,portMAX_DELAY);
    if ((event->kind==GL_EVENT_CONNECTED && !event->value) ||
        (event->kind==GL_EVENT_BUTTON && event->value) ||
        (event->kind==GL_EVENT_COMMAND && (event->command.opcode==GL_CANCEL ||
         (event->command.opcode==GL_CONSENT && event->command.argument==0))) ||
        (event->kind==GL_EVENT_SESSION && event->session.opcode==3)) {
        /* Revoke synchronously even if the worker is busy; drop queued commands from the old link. */
        if (event->kind==GL_EVENT_CONNECTED) gl_connected(&device,false);
        else if (event->kind==GL_EVENT_BUTTON) gl_button(&device,true,now_ms());
        else if(event->kind==GL_EVENT_COMMAND) gl_apply(&device,&event->command,now_ms());
        else gl_button(&device,true,now_ms());
        if(event->kind==GL_EVENT_SESSION)gl_media_service_command(&event->session,device.connected);
        else gl_media_service_revoke();
        xQueueReset(events); xSemaphoreGive(state_lock); return true;
    }
    gl_event queued=*event; queued.epoch=device.epoch;
    bool success=xQueueSend(events,&queued,0)==pdTRUE;
    if (!success) gl_error_push(&device,GL_QUEUE_FULL,now_ms());
    xSemaphoreGive(state_lock); return success;
}
static bool capture_authorize(void *context) {
    uint32_t epoch=((capture_context *)context)->epoch;
    xSemaphoreTake(state_lock,portMAX_DELAY);
    if (device.epoch==epoch && device.capture_requested && device.connected && device.consent) return true;
    xSemaphoreGive(state_lock); return false;
}
static void capture_unlock(void *context) { (void)context; xSemaphoreGive(state_lock); }
static bool consume_frame(const uint8_t *jpeg,size_t length,void *context) {
    capture_context *capture=context;
    xSemaphoreTake(state_lock,portMAX_DELAY);
    bool allowed=device.epoch==capture->epoch && device.consent && device.connected && device.capture_requested && device.privacy_verified;
    if(allowed) capture->published=gl_media_service_publish(jpeg,length,capture->request_id,true);
    xSemaphoreGive(state_lock);return capture->published;
}
void gl_status_snapshot(uint8_t out[GL_STATUS_SIZE]) {
    xSemaphoreTake(state_lock,portMAX_DELAY); gl_encode_status(&device,now_ms(),out); xSemaphoreGive(state_lock);
}
void app_main(void) {
    const gl_board *board=gl_board_profile();
    /* At boot only EVT-0 has an external camera rail. EYE/DevKit pins stay untouched. */
    if (board->configured && board->cam_pwr_en>=0) ESP_ERROR_CHECK(gl_camera_power_off(board));
    events=xQueueCreate(8,sizeof(gl_event)); state_lock=xSemaphoreCreateMutex();
    configASSERT(events && state_lock);
    gl_init(&device,board->configured,board->privacy_interlock_verified);
    gl_media_service_init();
    esp_err_t err=nvs_flash_init();
    if (err==ESP_ERR_NVS_NO_FREE_PAGES || err==ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase()); err=nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    ESP_LOGI("glasses","board=%s privacy_interlock=NOT_VERIFIED battery=UNKNOWN audio=UNCONFIGURED display_ready=%d",board->name,gl_display_ready(&display));
    ESP_ERROR_CHECK(gl_ble_start()); gl_button_start();
    gl_event event;
    for (;;) {
        if (xQueueReceive(events,&event,pdMS_TO_TICKS(1000))==pdTRUE) {
            xSemaphoreTake(state_lock,portMAX_DELAY);
            if (event.epoch!=device.epoch) { xSemaphoreGive(state_lock); continue; }
            if (event.kind==GL_EVENT_CONNECTED) gl_connected(&device,event.value);
            else if (event.kind==GL_EVENT_COMMAND) gl_apply_at_epoch(&device,&event.command,event.epoch,now_ms());
            else if (event.kind==GL_EVENT_BUTTON) gl_button(&device,event.value,now_ms());
            else if(event.kind==GL_EVENT_PAIR) gl_media_service_pair_window();
            else if(event.kind==GL_EVENT_SESSION) gl_media_service_command(&event.session,device.connected);
            bool acquire=device.capture_requested;
            capture_context capture={device.epoch,device.request_id,false};
            xSemaphoreGive(state_lock);
            if (acquire) {
                size_t frame_bytes=0;
                gl_capture_gate gate={capture_authorize,capture_unlock,&capture,consume_frame};
                esp_err_t camera_result=gl_camera_capture(board,&frame_bytes,&gate);
                xSemaphoreTake(state_lock,portMAX_DELAY);
                if (device.epoch==capture.epoch) gl_capture_finished_with_media(&device,camera_result==ESP_OK,capture.published,now_ms());
                xSemaphoreGive(state_lock);
                /* Only non-sensitive numeric metadata, never JPEG contents. */
                ESP_LOGI("glasses","capture_result=%d bytes=%u media_retained=%d",camera_result,(unsigned)frame_bytes,capture.published);
            }
        }
        gl_media_service_tick();gl_ble_notify();
    }
}
