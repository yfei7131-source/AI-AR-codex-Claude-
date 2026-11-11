#include "media_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned tests;
#define TEST(name) static void name(void)
#define RUN(name) do{name();tests++;printf("PASS %s\n",#name);}while(0)
static const char token[]="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static const char digest[]="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static const char auth[]="Bearer 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
/* Header/end-only fixture exercises storage contracts, not JPEG decoding or physical capture. */
static const uint8_t fixture[]={0xff,0xd8,1,2,3,4,0xff,0xd9};
static void ready(gl_media_store *s) { gl_media_init(s);assert(gl_media_open(s,token,10000,0)); }
TEST(v2_codec_has_distinct_version_and_reserved_checks) {
    uint8_t b[20]={2,1,0x34,0x12,0xe8,3};gl_session_command c;
    assert(gl_session_decode(b,20,&c)&&c.request_id==0x1234&&c.ttl_ms==1000);
    b[19]=1;assert(!gl_session_decode(b,20,&c));b[19]=0;b[0]=1;assert(!gl_session_decode(b,20,&c));
    b[0]=2;assert(!gl_session_decode(b,19,&c));b[1]=2;assert(!gl_session_decode(b,20,&c));
    b[4]=b[5]=0;assert(gl_session_decode(b,20,&c));b[1]=4;assert(!gl_session_decode(b,20,&c));
}
TEST(session_json_correlates_ready_and_errors_with_exact_request_id) {
    char json[512];
    assert(gl_session_error_json(json,sizeof(json),0,"disabled")>0&&strstr(json,"\"request_id\":0,"));
    assert(gl_session_error_json(json,sizeof(json),65535,"revoked")>0&&strstr(json,"\"request_id\":65535,")&&strstr(json,"\"ready\":false"));
    assert(gl_session_ready_json(json,sizeof(json),42,"AIAR-test","0123456789abcdef",token,30000)>0);
    assert(strstr(json,"\"request_id\":42,")&&strstr(json,"\"ready\":true")&&strstr(json,token));
}
TEST(session_json_rejects_truncation_or_injected_fields) {
    char json[512],tiny[8];
    assert(!gl_session_error_json(tiny,sizeof(tiny),1,"revoked")&&tiny[0]==0);
    assert(!gl_session_error_json(json,sizeof(json),1,"bad\"injected"));
    assert(!gl_session_ready_json(json,sizeof(json),1,"AIAR-test","01234567",token,0));
    assert(!gl_session_ready_json(json,sizeof(json),1,"AIAR-test","01234567",token,120001));
}
TEST(last_processed_session_id_survives_expiry_and_revoke) {
    gl_media_store s;gl_media_init(&s);assert(s.session_request_id==0);
    s.session_request_id=77;assert(gl_media_open(&s,token,1000,0));assert(s.session_request_id==77);
    gl_media_tick(&s,1000);assert(!s.active&&s.session_request_id==77);
    s.session_request_id=78;gl_media_revoke(&s);assert(s.session_request_id==78);
}
TEST(disabled_store_has_no_token_or_frame) {
    gl_media_store s;gl_media_init(&s);assert(!s.active&&!s.length&&!s.frame_id);
    assert(!gl_media_authorized(&s,auth,0));
}
TEST(token_strict_and_no_query_token_substitution) {
    gl_media_store s;ready(&s);assert(gl_media_authorized(&s,auth,1));
    assert(!gl_media_authorized(&s,token,1));assert(!gl_media_authorized(&s,"Bearer bad",1));
    char wrong[72];memcpy(wrong,auth,72);wrong[70]='0';assert(!gl_media_authorized(&s,wrong,1));
}
TEST(invalid_session_does_not_overwrite_existing_lease) {
    gl_media_store s;ready(&s);uint32_t expiry=s.expires_at;
    assert(!gl_media_open(&s,"wrong",10000,1));assert(!gl_media_open(&s,token,120001,1));assert(!gl_media_open(&s,token,999,1));
    assert(s.expires_at==expiry&&gl_media_authorized(&s,auth,1));
}
TEST(expiry_wipes_token_and_prevents_read) {
    gl_media_store s;ready(&s);assert(!gl_media_authorized(&s,auth,10000));
    assert(!s.active&&s.token[0]==0);
}
TEST(lease_expiry_handles_uptime_wrap) {
    gl_media_store s;gl_media_init(&s);assert(gl_media_open(&s,token,1000,UINT32_MAX-500));
    assert(gl_media_authorized(&s,auth,100));assert(!gl_media_authorized(&s,auth,500));
}
TEST(unreviewed_capture_cannot_publish_fixture) {
    gl_media_store s;ready(&s);uint8_t buffer[8];
    assert(!gl_media_publish(&s,buffer,8,fixture,8,digest,2,false,1));assert(!s.length&&!s.frame_id);
}
TEST(frame_publish_requires_bound_storage_jpeg_markers_and_hash_shape) {
    gl_media_store s;ready(&s);uint8_t buffer[8],bad[8]={0};
    assert(!gl_media_publish(&s,buffer,7,fixture,8,digest,2,true,1));
    assert(!gl_media_publish(&s,buffer,8,bad,8,digest,2,true,1));
    assert(!gl_media_publish(&s,buffer,8,fixture,8,"bad",2,true,1));
    assert(!gl_media_publish(&s,buffer,GL_MEDIA_MAX_BYTES+1,fixture,GL_MEDIA_MAX_BYTES+1,digest,2,true,1));
    assert(gl_media_publish(&s,buffer,8,fixture,8,digest,42,true,1));
    assert(s.capture_request_id==42&&s.frame_id==1&&s.length==8&&!memcmp(buffer,fixture,8));
}
TEST(frame_delete_wipes_bytes_but_keeps_session) {
    gl_media_store s;ready(&s);uint8_t buffer[8];assert(gl_media_publish(&s,buffer,8,fixture,8,digest,2,true,1));
    gl_media_clear_frame(&s);for(unsigned i=0;i<8;i++)assert(buffer[i]==0);
    assert(!s.frame_id&&!s.length&&gl_media_authorized(&s,auth,2));
}
TEST(revoke_wipes_frame_token_and_changes_epoch) {
    gl_media_store s;ready(&s);uint8_t buffer[8];assert(gl_media_publish(&s,buffer,8,fixture,8,digest,2,true,1));
    uint32_t epoch=s.epoch;gl_media_revoke(&s);assert(s.epoch!=epoch&&!s.length&&!s.active&&s.token[0]==0);
    for(unsigned i=0;i<8;i++)assert(buffer[i]==0);
}
TEST(frame_ttl_is_15_seconds_even_in_long_session) {
    gl_media_store s;gl_media_init(&s);assert(gl_media_open(&s,token,120000,0));uint8_t buffer[8];
    assert(gl_media_publish(&s,buffer,8,fixture,8,digest,2,true,1));gl_media_tick(&s,15001);
    assert(!s.length&&s.active&&buffer[0]==0);
}
TEST(frame_ids_change_and_old_id_is_not_readable) {
    gl_media_store s;ready(&s);uint8_t buffer[8],out[8];size_t offset,count;
    assert(gl_media_publish(&s,buffer,8,fixture,8,digest,2,true,1));uint32_t old=s.frame_id;
    assert(gl_media_publish(&s,buffer,8,fixture,8,digest,3,true,2));assert(s.frame_id!=old);
    assert(gl_media_copy(&s,auth,old,"bytes=0-7",3,out,8,&offset,&count)==404);
}
TEST(uri_requires_exact_nonzero_u32_id_no_external_url) {
    uint32_t id;assert(gl_media_frame_id("/v1/media/frame/4294967295",&id)&&id==UINT32_MAX);
    const char *bad[]={"/v1/media/frame/0","/v1/media/frame/4294967296","/v1/media/frame/1?token=x","https://example.com/1","/v1/media/frame/-1","/v1/media/frame/1/"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)assert(!gl_media_frame_id(bad[i],&id));
}
TEST(range_strict_bounded_and_overflow_safe) {
    size_t start,count;assert(gl_media_range("bytes=0-16383",20000,&start,&count)&&count==16384);
    const char *bad[]={"bytes=0-16384","bytes=9-8","bytes=-4","bytes=4-","bytes=0-1,4-5","bytes= 0-1","bytes=0-20000","bytes=184467440737095516160-9"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)assert(!gl_media_range(bad[i],20000,&start,&count));
}
TEST(chunks_reassemble_exactly_and_need_current_token_each_time) {
    gl_media_store s;ready(&s);uint8_t buffer[8],out[8]={0};size_t offset,count;
    assert(gl_media_publish(&s,buffer,8,fixture,8,digest,2,true,1));uint32_t id=s.frame_id;
    assert(gl_media_copy(&s,auth,id,"bytes=0-3",2,out,8,&offset,&count)==206&&offset==0&&count==4);
    assert(gl_media_copy(&s,auth,id,"bytes=4-7",3,out+4,4,&offset,&count)==206&&offset==4&&count==4);
    assert(!memcmp(out,fixture,8));gl_media_revoke(&s);
    assert(gl_media_copy(&s,auth,id,"bytes=4-7",4,out,8,&offset,&count)==401);
}
int main(void) {
    RUN(v2_codec_has_distinct_version_and_reserved_checks);RUN(disabled_store_has_no_token_or_frame);
    RUN(session_json_correlates_ready_and_errors_with_exact_request_id);RUN(session_json_rejects_truncation_or_injected_fields);
    RUN(last_processed_session_id_survives_expiry_and_revoke);
    RUN(token_strict_and_no_query_token_substitution);RUN(invalid_session_does_not_overwrite_existing_lease);
    RUN(expiry_wipes_token_and_prevents_read);RUN(lease_expiry_handles_uptime_wrap);RUN(unreviewed_capture_cannot_publish_fixture);
    RUN(frame_publish_requires_bound_storage_jpeg_markers_and_hash_shape);RUN(frame_delete_wipes_bytes_but_keeps_session);
    RUN(revoke_wipes_frame_token_and_changes_epoch);RUN(frame_ttl_is_15_seconds_even_in_long_session);
    RUN(frame_ids_change_and_old_id_is_not_readable);RUN(uri_requires_exact_nonzero_u32_id_no_external_url);
    RUN(range_strict_bounded_and_overflow_safe);RUN(chunks_reassemble_exactly_and_need_current_token_each_time);
    printf("%u/%u media host tests passed (fixtures only; no physical capture)\n",tests,tests);return 0;
}
