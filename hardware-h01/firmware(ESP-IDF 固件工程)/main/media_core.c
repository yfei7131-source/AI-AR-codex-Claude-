#include "media_core.h"
#include <string.h>
#include <stdio.h>
static bool expired(uint32_t now,uint32_t deadline) { return (int32_t)(now-deadline)>=0; }
static void wipe(void *p,size_t n) { volatile uint8_t *v=p; while(n--) *v++=0; }
static bool hex64(const char *s) {
    if (!s || strlen(s)!=64) return false;
    for(size_t i=0;i<64;i++) if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f'))) return false;
    return true;
}
static bool safe_ascii(const char *s,size_t max) {
    if(!s||!s[0]||strlen(s)>max)return false;
    for(;*s;s++)if(!((*s>='a'&&*s<='z')||(*s>='A'&&*s<='Z')||(*s>='0'&&*s<='9')||*s=='_'||*s=='-'))return false;
    return true;
}
static size_t json_length(char *out,size_t capacity,int length) {
    if(length<0||(size_t)length>=capacity) { if(capacity)out[0]=0;return 0; }
    return (size_t)length;
}
size_t gl_session_error_json(char *out,size_t capacity,uint16_t request_id,const char *error) {
    if(!out||!capacity||!safe_ascii(error,48))return 0;
    return json_length(out,capacity,snprintf(out,capacity,"{\"version\":2,\"request_id\":%u,\"ready\":false,\"error\":\"%s\"}",(unsigned)request_id,error));
}
size_t gl_session_ready_json(char *out,size_t capacity,uint16_t request_id,const char *ssid,
                             const char *passphrase,const char *token,uint32_t remaining_ms) {
    if(!out||!capacity||!safe_ascii(ssid,32)||!safe_ascii(passphrase,63)||strlen(passphrase)<8||!hex64(token)||!remaining_ms||remaining_ms>GL_MEDIA_MAX_TTL)return 0;
    return json_length(out,capacity,snprintf(out,capacity,"{\"version\":2,\"request_id\":%u,\"ready\":true,\"ssid\":\"%s\",\"passphrase\":\"%s\",\"base_url\":\"http://192.168.4.1\",\"token\":\"%s\",\"expires_in_ms\":%lu}",
                      (unsigned)request_id,ssid,passphrase,token,(unsigned long)remaining_ms));
}
bool gl_session_decode(const uint8_t *b,size_t n,gl_session_command *out) {
    if(!b||!out||n!=20||b[0]!=2||b[1]<1||b[1]>3) return false;
    for(size_t i=8;i<20;i++) if(b[i]) return false;
    uint32_t ttl=(uint32_t)b[4]|(uint32_t)b[5]<<8|(uint32_t)b[6]<<16|(uint32_t)b[7]<<24;
    if(b[1]==1 ? (ttl<1000||ttl>GL_MEDIA_MAX_TTL) : ttl!=0) return false;
    *out=(gl_session_command){b[1],(uint16_t)((uint16_t)b[2]|(uint16_t)b[3]<<8),ttl}; return true;
}
void gl_media_init(gl_media_store *s) { memset(s,0,sizeof(*s)); }
void gl_media_clear_frame(gl_media_store *s) {
    if(s->buffer && s->length) wipe(s->buffer,s->length);
    s->length=0; s->frame_id=0; s->capture_request_id=0; s->frame_expires_at=0; wipe(s->sha256,sizeof(s->sha256));
}
void gl_media_revoke(gl_media_store *s) {
    gl_media_clear_frame(s); wipe(s->token,sizeof(s->token)); s->active=false; s->expires_at=0; s->epoch++;
}
bool gl_media_open(gl_media_store *s,const char *token,uint32_t ttl,uint32_t now) {
    if(!hex64(token)||ttl<1000||ttl>GL_MEDIA_MAX_TTL) return false;
    gl_media_revoke(s); memcpy(s->token,token,65); s->active=true; s->expires_at=now+ttl; return true;
}
void gl_media_tick(gl_media_store *s,uint32_t now) {
    if(s->active&&expired(now,s->expires_at)) gl_media_revoke(s);
    else if(s->length&&expired(now,s->frame_expires_at)) gl_media_clear_frame(s);
}
bool gl_media_authorized(gl_media_store *s,const char *authorization,uint32_t now) {
    gl_media_tick(s,now);
    if(!s->active||!authorization||strlen(authorization)!=71||memcmp(authorization,"Bearer ",7)) return false;
    unsigned mismatch=0;for(size_t i=0;i<64;i++) mismatch|=(unsigned)(uint8_t)(authorization[i+7]^s->token[i]);
    return mismatch==0;
}
bool gl_media_publish(gl_media_store *s,uint8_t *storage,size_t capacity,const uint8_t *jpeg,size_t length,
                      const char *sha256,uint16_t req,bool reviewed,uint32_t now) {
    gl_media_tick(s,now);
    if(!s->active||!reviewed||!storage||!jpeg||length<4||length>GL_MEDIA_MAX_BYTES||capacity<length||!hex64(sha256)||
       jpeg[0]!=0xff||jpeg[1]!=0xd8||jpeg[length-2]!=0xff||jpeg[length-1]!=0xd9) return false;
    gl_media_clear_frame(s); s->buffer=storage;s->capacity=capacity;memcpy(s->buffer,jpeg,length);s->length=length;
    memcpy(s->sha256,sha256,65);s->capture_request_id=req;
    if(++s->next_frame_id==0) s->next_frame_id=1;
    s->frame_id=s->next_frame_id;s->frame_expires_at=now+GL_MEDIA_FRAME_TTL;return true;
}
static bool decimal(const char **text,size_t *out) {
    const char *s=*text;size_t value=0;
    if(*s<'0'||*s>'9') return false;
    while(*s>='0'&&*s<='9') { size_t digit=(size_t)(*s-'0');if(value>(SIZE_MAX-digit)/10) return false;value=value*10+digit;s++; }
    *text=s;*out=value;return true;
}
bool gl_media_frame_id(const char *uri,uint32_t *id) {
    const char *prefix="/v1/media/frame/";size_t value;
    if(!uri||!id||strncmp(uri,prefix,strlen(prefix))) return false;
    const char *p=uri+strlen(prefix);
    if(!decimal(&p,&value)||*p||!value||value>UINT32_MAX) return false;
    *id=(uint32_t)value;return true;
}
bool gl_media_range(const char *header,size_t total,size_t *offset,size_t *length) {
    if(!header||!offset||!length||strncmp(header,"bytes=",6)) return false;
    const char *p=header+6;size_t start,end;
    if(!decimal(&p,&start)||*p++!='-'||!decimal(&p,&end)||*p||start>end||end>=total||end-start>=GL_MEDIA_MAX_CHUNK) return false;
    *offset=start;*length=end-start+1;return true;
}
int gl_media_copy(gl_media_store *s,const char *auth,uint32_t id,const char *range,uint32_t now,
                  uint8_t *out,size_t capacity,size_t *offset,size_t *copied) {
    if(!gl_media_authorized(s,auth,now)) return 401;
    if(!s->length||s->frame_id!=id) return 404;
    size_t start,length;
    if(!gl_media_range(range,s->length,&start,&length)||!out||capacity<length||!offset||!copied) return 416;
    memcpy(out,s->buffer+start,length);*offset=start;*copied=length;return 206;
}
