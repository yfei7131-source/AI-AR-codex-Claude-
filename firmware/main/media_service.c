#include "media_service.h"
#include "runtime.h"
#include "sdkconfig.h"
#include "esp_http_server.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "mbedtls/sha256.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef CONFIG_GL_MEDIA_DEV_AP
static const bool enabled=true;
#else
static const bool enabled=false;
#endif
static gl_media_store media;
static SemaphoreHandle_t mutex;
static httpd_handle_t server;
static bool wifi_initialized, wifi_running;
static uint32_t pair_deadline;
static bool pair_open;
static uint16_t open_request;
static char session_json[512],ssid[32],passphrase[33];
static uint32_t clock_ms(void) { return (uint32_t)(esp_timer_get_time()/1000); }
static bool before(uint32_t now,uint32_t deadline) { return (int32_t)(now-deadline)<0; }
static void lock(void) { xSemaphoreTake(mutex,portMAX_DELAY); }
static void unlock(void) { xSemaphoreGive(mutex); }
static void zero(void *p,size_t size) { volatile unsigned char *v=p;while(size--) *v++=0; }
static void free_frame(void) {
    gl_media_clear_frame(&media);free(media.buffer);media.buffer=NULL;media.capacity=0;
}
static void message(const char *error) {
    zero(session_json,sizeof(session_json));
    gl_session_error_json(session_json,sizeof(session_json),media.session_request_id,error);
}
static void cache_session(uint32_t now) {
    gl_media_tick(&media,now);
    if(!media.active) { message(enabled?"revoked":"disabled");return; }
    gl_session_ready_json(session_json,sizeof(session_json),media.session_request_id,ssid,passphrase,media.token,media.expires_at-now);
}
static void random_hex(char *out,size_t bytes) {
    static const char hex[]="0123456789abcdef";
    for(size_t i=0;i<bytes;i++) { uint8_t b=(uint8_t)esp_random();out[i*2]=hex[b>>4];out[i*2+1]=hex[b&15]; }
    out[bytes*2]=0;
}
static void revoke_locked(void) {
    gl_media_revoke(&media);free_frame();pair_open=false;zero(ssid,sizeof(ssid));zero(passphrase,sizeof(passphrase));message(enabled?"revoked":"disabled");
}
void gl_media_service_revoke(void) { if(!mutex)return;lock();revoke_locked();unlock(); }
static void wifi_event(void *context,esp_event_base_t base,int32_t id,void *data) {
    (void)context;(void)base;(void)data;
    if(id==WIFI_EVENT_AP_STADISCONNECTED) {
        gl_event event={.kind=GL_EVENT_BUTTON,.value=true};
        if(!gl_post_event(&event))gl_media_service_revoke();
    }
}
static bool request_headers(httpd_req_t *req,char authorization[72]) {
    char host[32];
    if(req->content_len || httpd_req_get_hdr_value_len(req,"Origin") ||
       httpd_req_get_hdr_value_str(req,"Host",host,sizeof(host))!=ESP_OK ||
       (strcmp(host,"192.168.4.1")&&strcmp(host,"192.168.4.1:80")) ||
       httpd_req_get_hdr_value_len(req,"Authorization")!=71 ||
       httpd_req_get_hdr_value_str(req,"Authorization",authorization,72)!=ESP_OK) return false;
    return true;
}
static esp_err_t reject(httpd_req_t *req,int code) {
    const char *status=code==401?"401 Unauthorized":code==404?"404 Not Found":code==416?"416 Range Not Satisfiable":"403 Forbidden";
    httpd_resp_set_status(req,status);httpd_resp_set_hdr(req,"Cache-Control","no-store");return httpd_resp_send(req,"",0);
}
static esp_err_t http_status(httpd_req_t *req) {
    char auth[72]={0},json[512];
    if(!request_headers(req,auth)) return reject(req,401);
    lock();uint32_t now=clock_ms();
    if(!gl_media_authorized(&media,auth,now)) { unlock();zero(auth,sizeof(auth));return reject(req,401); }
    if(!media.length) snprintf(json,sizeof(json),"{\"version\":1,\"source\":\"device\",\"captured\":false,\"frame\":null}");
    else snprintf(json,sizeof(json),"{\"version\":1,\"source\":\"device\",\"captured\":true,\"frame\":{\"frame_id\":%lu,\"request_id\":%u,\"length\":%u,\"sha256\":\"%s\",\"mime\":\"image/jpeg\",\"captured\":true,\"expires_in_ms\":%lu}}",
                  (unsigned long)media.frame_id,media.capture_request_id,(unsigned)media.length,media.sha256,(unsigned long)(media.frame_expires_at-now));
    httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");
    esp_err_t result=httpd_resp_send(req,json,HTTPD_RESP_USE_STRLEN);unlock();zero(auth,sizeof(auth));return result;
}
static esp_err_t http_frame(httpd_req_t *req) {
    char auth[72]={0};uint32_t id;
    if(!request_headers(req,auth)) return reject(req,401);
    if(!gl_media_frame_id(req->uri,&id)) { zero(auth,sizeof(auth));return reject(req,404); }
    lock();
    if(!gl_media_authorized(&media,auth,clock_ms())) { unlock();zero(auth,sizeof(auth));return reject(req,401); }
    if(!media.length||media.frame_id!=id) { unlock();zero(auth,sizeof(auth));return reject(req,404); }
    if(req->method==HTTP_DELETE) {
        free_frame();httpd_resp_set_status(req,"204 No Content");httpd_resp_set_hdr(req,"Cache-Control","no-store");
        esp_err_t result=httpd_resp_send(req,"",0);unlock();zero(auth,sizeof(auth));return result;
    }
    char range[80]={0};size_t offset=0,count=0;
    if(httpd_req_get_hdr_value_str(req,"Range",range,sizeof(range))!=ESP_OK || !gl_media_range(range,media.length,&offset,&count)) {
        unlock();zero(auth,sizeof(auth));return reject(req,416);
    }
    char content_range[96],etag[68];
    snprintf(content_range,sizeof(content_range),"bytes %u-%u/%u",(unsigned)offset,(unsigned)(offset+count-1),(unsigned)media.length);
    snprintf(etag,sizeof(etag),"\"%s\"",media.sha256);
    httpd_resp_set_status(req,"206 Partial Content");httpd_resp_set_type(req,"image/jpeg");
    httpd_resp_set_hdr(req,"Content-Range",content_range);httpd_resp_set_hdr(req,"ETag",etag);httpd_resp_set_hdr(req,"Cache-Control","no-store");
    /* Hold one lease transaction through a bounded <=16KiB send; revocation may wait <=2s socket timeout. */
    esp_err_t result=httpd_resp_send(req,(const char *)media.buffer+offset,(ssize_t)count);
    unlock();zero(auth,sizeof(auth));return result;
}
static esp_err_t start_network(void) {
    esp_err_t result;
    if(!wifi_initialized) {
        result=esp_netif_init();if(result!=ESP_OK)return result;
        result=esp_event_loop_create_default();if(result!=ESP_OK&&result!=ESP_ERR_INVALID_STATE)return result;
        if(!esp_netif_create_default_wifi_ap())return ESP_FAIL;
        wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();result=esp_wifi_init(&init);if(result!=ESP_OK)return result;
        result=esp_wifi_set_storage(WIFI_STORAGE_RAM);if(result!=ESP_OK)return result;
        result=esp_event_handler_register(WIFI_EVENT,WIFI_EVENT_AP_STADISCONNECTED,wifi_event,NULL);if(result!=ESP_OK)return result;
        wifi_initialized=true;
    }
    wifi_config_t config={0};
    snprintf((char *)config.ap.ssid,sizeof(config.ap.ssid),"%s",ssid);config.ap.ssid_len=strlen(ssid);
    snprintf((char *)config.ap.password,sizeof(config.ap.password),"%s",passphrase);
    config.ap.channel=1;config.ap.max_connection=1;config.ap.authmode=WIFI_AUTH_WPA2_PSK;config.ap.pmf_cfg.capable=true;
    result=esp_wifi_set_mode(WIFI_MODE_AP);if(result!=ESP_OK)return result;
    result=esp_wifi_set_config(WIFI_IF_AP,&config);zero(&config,sizeof(config));if(result!=ESP_OK)return result;
    result=esp_wifi_start();if(result!=ESP_OK)return result;wifi_running=true;
    result=esp_wifi_set_max_tx_power(CONFIG_GL_MEDIA_TX_POWER_QDBM);
    if(result!=ESP_OK)return result;
    int8_t actual_power=0;
    result=esp_wifi_get_max_tx_power(&actual_power);if(result!=ESP_OK)return result;
    ESP_LOGI("glasses","AP TX power limit requested=%d readback=%d quarter-dBm",
             CONFIG_GL_MEDIA_TX_POWER_QDBM,(int)actual_power);
    httpd_config_t http=HTTPD_DEFAULT_CONFIG();http.server_port=80;http.max_open_sockets=2;http.lru_purge_enable=true;
    http.recv_wait_timeout=2;http.send_wait_timeout=2;http.stack_size=6144;http.uri_match_fn=httpd_uri_match_wildcard;
    result=httpd_start(&server,&http);if(result!=ESP_OK)return result;
    const httpd_uri_t status={.uri="/v1/media/status",.method=HTTP_GET,.handler=http_status};
    const httpd_uri_t get={.uri="/v1/media/frame/*",.method=HTTP_GET,.handler=http_frame};
    const httpd_uri_t remove={.uri="/v1/media/frame/*",.method=HTTP_DELETE,.handler=http_frame};
    result=httpd_register_uri_handler(server,&status);if(result!=ESP_OK)return result;
    result=httpd_register_uri_handler(server,&get);if(result!=ESP_OK)return result;
    return httpd_register_uri_handler(server,&remove);
}
void gl_media_service_init(void) {
    mutex=xSemaphoreCreateMutex();configASSERT(mutex);gl_media_init(&media);message(enabled?"pairing_required":"disabled");
}
void gl_media_service_pair_window(void) {
    lock();if(enabled) { pair_deadline=clock_ms()+30000;pair_open=true;message("pairing_window_open"); }unlock();
}
void gl_media_service_command(const gl_session_command *c,bool connected) {
    lock();media.session_request_id=c->request_id; /* Mark only when this command is actually processed. */
    if(c->opcode==3) { revoke_locked();message("revoked");unlock();return; }
    uint32_t now=clock_ms();gl_media_tick(&media,now);
    if(!enabled) message("disabled");
    else if(!connected) message("ble_required");
    else if(c->opcode==2) cache_session(now);
    else if(media.active && c->request_id==open_request) cache_session(now);
    else if(!pair_open||!before(now,pair_deadline)||wifi_running) message("pairing_required");
    else {
        pair_open=false;char suffix[7],token[65];random_hex(suffix,3);snprintf(ssid,sizeof(ssid),"AIAR-%s",suffix);
        random_hex(passphrase,16);random_hex(token,32);
        if(gl_media_open(&media,token,c->ttl_ms,now) && start_network()==ESP_OK) {
            open_request=c->request_id;cache_session(clock_ms());
        } else { revoke_locked();message("wifi_start_failed"); }
        zero(token,sizeof(token));
    }
    unlock();
}
size_t gl_media_service_session(char *out,size_t capacity) {
    lock();gl_media_tick(&media,clock_ms());
    if(!media.active && strstr(session_json,"\"ready\":true")) { free_frame();message("expired"); }
    size_t length=strlen(session_json);
    if(capacity<=length) length=0;else memcpy(out,session_json,length+1);
    unlock();return length;
}
void gl_media_service_tick(void) {
    lock();gl_media_tick(&media,clock_ms());if(!media.length && media.buffer)free_frame();
    bool stop=wifi_running&&!media.active;
    if(stop) { zero(ssid,sizeof(ssid));zero(passphrase,sizeof(passphrase));message("revoked"); }
    unlock();
    if(stop) { if(server) { httpd_stop(server);server=NULL; }esp_wifi_stop();wifi_running=false; }
}
bool gl_media_service_publish(const uint8_t *jpeg,size_t length,uint16_t request_id,bool reviewed) {
    if(!reviewed||!jpeg||length<4||length>GL_MEDIA_MAX_BYTES)return false;
    lock();gl_media_tick(&media,clock_ms());if(!media.active) { unlock();return false; }
    uint8_t hash[32];char hex[65];
    if(mbedtls_sha256(jpeg,length,hash,0)!=0) { unlock();return false; }
    for(size_t i=0;i<32;i++)snprintf(hex+i*2,3,"%02x",hash[i]);
    uint8_t *buffer=malloc(length);if(!buffer) { zero(hash,sizeof(hash));zero(hex,sizeof(hex));unlock();return false; }
    free_frame();bool success=gl_media_publish(&media,buffer,length,jpeg,length,hex,request_id,reviewed,clock_ms());
    if(!success) { zero(buffer,length);free(buffer); }
    zero(hash,sizeof(hash));zero(hex,sizeof(hex));unlock();return success;
}
