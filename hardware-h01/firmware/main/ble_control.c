#include "runtime.h"
#include "media_service.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "nimble/nimble_npl.h"
#include "host/ble_hs.h"
#include "host/ble_store.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
#include <string.h>
/* UUID 8f13a001-6c55-4b8e-9d51-2f76a4b10000, little-endian NimBLE bytes. */
#define GL_UUID(n) BLE_UUID128_INIT(0x00,0x00,0xb1,0xa4,0x76,0x2f,0x51,0x9d,0x8e,0x4b,0x55,0x6c,n,0xa0,0x13,0x8f)
static const ble_uuid128_t service_uuid=GL_UUID(1), control_uuid=GL_UUID(2), status_uuid=GL_UUID(3);
static const ble_uuid128_t session_control_uuid=GL_UUID(4),session_info_uuid=GL_UUID(5);
static uint16_t connection=BLE_HS_CONN_HANDLE_NONE, status_handle;
static uint8_t address_type;
static bool subscribed;
void ble_store_config_init(void);
static struct ble_npl_event notify_event;
static void notify_on_host(struct ble_npl_event *event);
static void advertise(void);
static int access_value(uint16_t conn, uint16_t attr, struct ble_gatt_access_ctxt *ctxt, void *arg) {
    (void)conn; (void)attr;
    intptr_t tag=(intptr_t)arg;
    if(tag==3) {
        if(ctxt->op!=BLE_GATT_ACCESS_OP_READ_CHR)return BLE_ATT_ERR_READ_NOT_PERMITTED;
        char json[512];size_t length=gl_media_service_session(json,sizeof(json));
        int result=length&&os_mbuf_append(ctxt->om,json,(uint16_t)length)==0?0:BLE_ATT_ERR_INSUFFICIENT_RES;
        memset(json,0,sizeof(json));return result;
    }
    if(tag==2) {
        if(ctxt->op!=BLE_GATT_ACCESS_OP_WRITE_CHR)return BLE_ATT_ERR_WRITE_NOT_PERMITTED;
        uint8_t bytes[20];uint16_t length=0;gl_event event={.kind=GL_EVENT_SESSION};
        if(OS_MBUF_PKTLEN(ctxt->om)!=20||ble_hs_mbuf_to_flat(ctxt->om,bytes,sizeof(bytes),&length)!=0||!gl_session_decode(bytes,length,&event.session))return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
        return gl_post_event(&event)?0:BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    if (tag==1) {
        if (ctxt->op!=BLE_GATT_ACCESS_OP_WRITE_CHR) return BLE_ATT_ERR_WRITE_NOT_PERMITTED;
        uint8_t bytes[GL_CONTROL_SIZE]; uint16_t length=0; gl_event event={.kind=GL_EVENT_COMMAND};
        if (OS_MBUF_PKTLEN(ctxt->om)!=GL_CONTROL_SIZE || ble_hs_mbuf_to_flat(ctxt->om,bytes,sizeof(bytes),&length)!=0 ||
            !gl_decode_command(bytes,length,&event.command)) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
        return gl_post_event(&event) ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    if (ctxt->op!=BLE_GATT_ACCESS_OP_READ_CHR) return BLE_ATT_ERR_READ_NOT_PERMITTED;
    uint8_t bytes[GL_STATUS_SIZE]; gl_status_snapshot(bytes);
    return os_mbuf_append(ctxt->om,bytes,sizeof(bytes))==0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
}
static const struct ble_gatt_svc_def services[]={
    {.type=BLE_GATT_SVC_TYPE_PRIMARY,.uuid=&service_uuid.u,.characteristics=(struct ble_gatt_chr_def[]){
        {.uuid=&control_uuid.u,.access_cb=access_value,.arg=(void *)1,.flags=BLE_GATT_CHR_F_WRITE|BLE_GATT_CHR_F_WRITE_ENC},
        {.uuid=&status_uuid.u,.access_cb=access_value,.val_handle=&status_handle,.flags=BLE_GATT_CHR_F_READ|BLE_GATT_CHR_F_READ_ENC|BLE_GATT_CHR_F_NOTIFY},
        {.uuid=&session_control_uuid.u,.access_cb=access_value,.arg=(void *)2,.flags=BLE_GATT_CHR_F_WRITE|BLE_GATT_CHR_F_WRITE_ENC},
        {.uuid=&session_info_uuid.u,.access_cb=access_value,.arg=(void *)3,.flags=BLE_GATT_CHR_F_READ|BLE_GATT_CHR_F_READ_ENC},
        {0}}},
    {0}};
static int gap_event(struct ble_gap_event *event, void *arg) {
    (void)arg;
    gl_event message={.kind=GL_EVENT_CONNECTED};
    switch (event->type) {
        case BLE_GAP_EVENT_CONNECT:
            if (event->connect.status==0) {
                connection=event->connect.conn_handle; message.value=true; gl_post_event(&message);
                ble_gap_security_initiate(connection);
            } else advertise();
            break;
        case BLE_GAP_EVENT_DISCONNECT:
            connection=BLE_HS_CONN_HANDLE_NONE; subscribed=false; message.value=false; gl_post_event(&message); advertise(); break;
        case BLE_GAP_EVENT_SUBSCRIBE: subscribed=event->subscribe.cur_notify; break;
        case BLE_GAP_EVENT_ADV_COMPLETE: advertise(); break;
        default: break;
    }
    return 0;
}
static void advertise(void) {
    struct ble_hs_adv_fields fields={0};
    fields.flags=BLE_HS_ADV_F_DISC_GEN|BLE_HS_ADV_F_BREDR_UNSUP;
    fields.uuids128=(ble_uuid128_t *)&service_uuid; fields.num_uuids128=1; fields.uuids128_is_complete=1;
    if (ble_gap_adv_set_fields(&fields)!=0) return;
    struct ble_gap_adv_params params={0}; params.conn_mode=BLE_GAP_CONN_MODE_UND; params.disc_mode=BLE_GAP_DISC_MODE_GEN;
    ble_gap_adv_start(address_type,NULL,BLE_HS_FOREVER,&params,gap_event,NULL);
}
static void synchronized(void) { if (ble_hs_id_infer_auto(0,&address_type)==0) advertise(); }
static void reset(int reason) {
    (void)reason;connection=BLE_HS_CONN_HANDLE_NONE;subscribed=false;
    gl_event event={.kind=GL_EVENT_CONNECTED,.value=false};gl_post_event(&event);
}
static void host_task(void *param) { (void)param; nimble_port_run(); nimble_port_freertos_deinit(); }
esp_err_t gl_ble_start(void) {
    esp_err_t result=nimble_port_init(); if (result!=ESP_OK) return result;
    ble_hs_cfg.sync_cb=synchronized;ble_hs_cfg.reset_cb=reset; ble_hs_cfg.sm_bonding=1; ble_hs_cfg.sm_sc=1; ble_hs_cfg.sm_sc_only=1;
    ble_hs_cfg.sm_io_cap=BLE_HS_IO_NO_INPUT_OUTPUT;
    ble_hs_cfg.store_status_cb=ble_store_util_status_rr;
    ble_hs_cfg.sm_our_key_dist|=BLE_SM_PAIR_KEY_DIST_ENC|BLE_SM_PAIR_KEY_DIST_ID;
    ble_hs_cfg.sm_their_key_dist|=BLE_SM_PAIR_KEY_DIST_ENC|BLE_SM_PAIR_KEY_DIST_ID;
    ble_store_config_init();
    ble_svc_gap_init(); ble_svc_gatt_init(); ble_svc_gap_device_name_set("AIAR-Glasses-Dev");
    ble_npl_event_init(&notify_event,notify_on_host,NULL);
    if (ble_gatts_count_cfg(services)!=0 || ble_gatts_add_svcs(services)!=0) return ESP_FAIL;
    nimble_port_freertos_init(host_task); return ESP_OK;
}
void gl_ble_notify(void) {
    ble_npl_eventq_put(nimble_port_get_dflt_eventq(),&notify_event);
}
static void notify_on_host(struct ble_npl_event *event) {
    (void)event;
    if (connection==BLE_HS_CONN_HANDLE_NONE || !subscribed) return;
    struct ble_gap_conn_desc desc;
    if (ble_gap_conn_find(connection,&desc)!=0 || !desc.sec_state.encrypted) return;
    uint8_t bytes[GL_STATUS_SIZE]; gl_status_snapshot(bytes);
    struct os_mbuf *om=ble_hs_mbuf_from_flat(bytes,sizeof(bytes));
    if (om) ble_gatts_notify_custom(connection,status_handle,om);
}
