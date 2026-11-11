#include "core.h"
#include <string.h>

static uint16_t read16(const uint8_t *p) { return (uint16_t)p[0] | (uint16_t)((uint16_t)p[1]<<8); }
static uint32_t read32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24; }
static void write16(uint8_t *p, uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
static void write32(uint8_t *p, uint32_t v) { for (unsigned i=0;i<4;i++) p[i]=(uint8_t)(v>>(8*i)); }

bool gl_decode_command(const uint8_t *bytes, size_t length, gl_command *out) {
    if (!bytes || !out || length != GL_CONTROL_SIZE || bytes[0] != 1) return false;
    if (bytes[1]<GL_STATUS || bytes[1]>GL_CLEAR_LOG) return false;
    uint32_t arg=read32(bytes+4);
    if ((bytes[1]==GL_CONSENT && arg>1) || (bytes[1]!=GL_CONSENT && arg!=0)) return false;
    out->opcode=bytes[1]; out->request_id=read16(bytes+2); out->argument=arg;
    return true;
}
void gl_init(gl_device *d, bool board_ready, bool privacy_verified) {
    memset(d,0,sizeof(*d)); d->board_ready=board_ready; d->privacy_verified=privacy_verified;
}
void gl_connected(gl_device *d, bool connected) {
    d->connected=connected;
    d->consent=false; d->capture_requested=false; d->state=GL_IDLE;
    if (!connected) { d->epoch++; d->has_last_request=false; d->recent_count=0; d->recent_head=0; }
}
void gl_error_push(gl_device *d, uint8_t code, uint32_t now_ms) {
    d->last_error=code;
    if (code==GL_OK) return;
    d->state=GL_ERROR; d->errors++;
    d->log[d->log_head]=(gl_error_record){now_ms,d->request_id,code};
    d->log_head=(d->log_head+1)%GL_LOG_CAPACITY;
    if (d->log_count<GL_LOG_CAPACITY) d->log_count++;
}
bool gl_error_get(const gl_device *d, size_t index, gl_error_record *out) {
    if (!out || index>=d->log_count) return false;
    size_t oldest=(d->log_head+GL_LOG_CAPACITY-d->log_count)%GL_LOG_CAPACITY;
    *out=d->log[(oldest+index)%GL_LOG_CAPACITY]; return true;
}
uint8_t gl_capture_allowed(const gl_device *d) {
    if (!d->board_ready) return GL_BOARD_MISSING;
    if (!d->privacy_verified) return GL_PRIVACY_UNVERIFIED;
    if (!d->connected) return GL_NOT_CONNECTED;
    if (!d->consent) return GL_NO_CONSENT;
    if (d->capture_requested || d->state==GL_CAPTURING) return GL_BUSY;
    return GL_OK;
}
static uint8_t start_capture(gl_device *d, uint32_t now_ms) {
    uint8_t result=gl_capture_allowed(d);
    if (result) gl_error_push(d,result,now_ms);
    else { d->capture_requested=true; d->state=GL_CAPTURING; d->last_error=GL_OK; }
    return result;
}
static void remember_request(gl_device *d, uint16_t id) {
    d->has_last_request=true; d->last_request_id=id;
    d->recent_ids[d->recent_head]=id;
    d->recent_head=(d->recent_head+1)%GL_LOG_CAPACITY;
    if (d->recent_count<GL_LOG_CAPACITY) d->recent_count++;
}
uint8_t gl_apply(gl_device *d, const gl_command *c, uint32_t now_ms) {
    if (!c || c->opcode<GL_STATUS || c->opcode>GL_CLEAR_LOG ||
        (c->opcode==GL_CONSENT ? c->argument>1 : c->argument!=0)) {
        gl_error_push(d,GL_BAD_FRAME,now_ms); return GL_BAD_FRAME;
    }
    d->request_id=c->request_id;
    if (c->opcode==GL_STATUS) return GL_OK;
    if (!d->connected) { gl_error_push(d,GL_NOT_CONNECTED,now_ms); return GL_NOT_CONNECTED; }
    bool duplicate=false;
    for (size_t i=0;i<d->recent_count;i++) if (d->recent_ids[i]==c->request_id) duplicate=true;
    /* Safety revocation is idempotent even when the caller repeats an ID. */
    if (c->opcode==GL_CANCEL || (c->opcode==GL_CONSENT && c->argument==0)) {
        if (!duplicate) remember_request(d,c->request_id);
        d->epoch++; d->capture_requested=false; d->state=GL_IDLE; d->last_error=GL_OK;
        if (c->opcode==GL_CONSENT) d->consent=false;
        return GL_OK;
    }
    if (duplicate) return GL_DUPLICATE;
    remember_request(d,c->request_id);
    switch (c->opcode) {
        case GL_CAPTURE: return start_capture(d,now_ms);
        case GL_CANCEL: d->capture_requested=false; d->state=GL_IDLE; d->last_error=GL_OK; return GL_OK;
        case GL_CONSENT:
            d->consent=c->argument==1;
            if (!d->consent) { d->capture_requested=false; d->state=GL_IDLE; }
            d->last_error=GL_OK; return GL_OK;
        case GL_CLEAR_LOG:
            memset(d->log,0,sizeof(d->log)); d->log_head=0; d->log_count=0; d->last_error=GL_OK; return GL_OK;
        default: return GL_BAD_FRAME;
    }
}
uint8_t gl_apply_at_epoch(gl_device *d, const gl_command *c, uint32_t epoch, uint32_t now_ms) {
    return epoch==d->epoch ? gl_apply(d,c,now_ms) : GL_STALE_EVENT;
}
uint8_t gl_button(gl_device *d, bool long_press, uint32_t now_ms) {
    if (long_press) { d->epoch++; d->capture_requested=false; d->consent=false; d->state=GL_IDLE; d->last_error=GL_OK; return GL_OK; }
    return start_capture(d,now_ms);
}
void gl_capture_finished(gl_device *d, bool success, uint32_t now_ms) {
    gl_capture_finished_with_media(d,success,false,now_ms);
}
void gl_capture_finished_with_media(gl_device *d,bool success,bool media_available,uint32_t now_ms) {
    if (!d->capture_requested || !d->connected || !d->consent) return;
    d->capture_requested=false;
    if (success) {
        d->captures++;
        if(media_available) { d->state=GL_IDLE;d->last_error=GL_OK; }
        else gl_error_push(d,GL_MEDIA_NOT_CONFIGURED,now_ms);
    }
    else gl_error_push(d,GL_CAMERA_FAILED,now_ms);
}
void gl_encode_status(const gl_device *d, uint32_t now_ms, uint8_t out[GL_STATUS_SIZE]) {
    memset(out,0,GL_STATUS_SIZE); out[0]=1; out[1]=d->state;
    out[2]=(uint8_t)((d->connected?1:0)|(d->consent?2:0)|(d->board_ready?4:0)|(d->privacy_verified?8:0));
    out[3]=d->last_error; write16(out+4,d->request_id); out[6]=255; /* battery unknown, never fake 100% */
    out[7]=(uint8_t)d->log_count; write32(out+8,now_ms); write32(out+12,d->captures); write32(out+16,d->errors);
}
