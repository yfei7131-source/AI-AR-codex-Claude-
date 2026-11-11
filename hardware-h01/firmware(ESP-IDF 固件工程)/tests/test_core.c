#include "core.h"
#include "display_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned tests;
#define TEST(name) static void name(void)
#define RUN(name) do { name(); tests++; printf("PASS %s\n",#name); } while(0)
static gl_command cmd(uint8_t op, uint16_t id, uint32_t arg) { return (gl_command){op,id,arg}; }
TEST(protocol_valid_little_endian) {
    const uint8_t frame[]={1,GL_CONSENT,0x34,0x12,1,0,0,0}; gl_command c;
    assert(gl_decode_command(frame,8,&c)); assert(c.opcode==GL_CONSENT && c.request_id==0x1234 && c.argument==1);
}
TEST(protocol_rejects_bad_version_length_opcode_argument) {
    uint8_t frame[]={1,GL_STATUS,0,0,0,0,0,0}; gl_command c;
    assert(!gl_decode_command(NULL,8,&c)); assert(!gl_decode_command(frame,7,&c)); assert(!gl_decode_command(frame,9,&c));
    frame[0]=2; assert(!gl_decode_command(frame,8,&c)); frame[0]=1;
    frame[1]=6; assert(!gl_decode_command(frame,8,&c)); frame[1]=GL_CONSENT; frame[4]=2;
    assert(!gl_decode_command(frame,8,&c)); frame[1]=GL_CAPTURE; frame[4]=1; assert(!gl_decode_command(frame,8,&c));
}
TEST(unconfigured_never_captures) {
    gl_device d; gl_init(&d,false,false); gl_connected(&d,true); d.consent=true;
    assert(gl_button(&d,false,1)==GL_BOARD_MISSING); assert(!d.capture_requested);
}
TEST(privacy_unverified_never_captures) {
    gl_device d; gl_init(&d,true,false); gl_connected(&d,true); d.consent=true;
    gl_command c=cmd(GL_CAPTURE,1,0); assert(gl_apply(&d,&c,1)==GL_PRIVACY_UNVERIFIED); assert(!d.capture_requested);
}
TEST(capture_requires_connection_and_consent) {
    gl_device d; gl_init(&d,true,true); assert(gl_button(&d,false,1)==GL_NOT_CONNECTED);
    gl_connected(&d,true); assert(gl_button(&d,false,2)==GL_NO_CONSENT);
    gl_command c=cmd(GL_CONSENT,1,1); assert(gl_apply(&d,&c,3)==GL_OK);
    c=cmd(GL_CAPTURE,2,0); assert(gl_apply(&d,&c,4)==GL_OK && d.capture_requested && d.state==GL_CAPTURING);
}
TEST(replay_after_another_command_cannot_reapply_consent) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true);
    gl_command a=cmd(GL_CONSENT,10,1), b=cmd(GL_CONSENT,11,0);
    assert(gl_apply(&d,&a,1)==GL_OK); assert(gl_apply(&d,&b,2)==GL_OK);
    assert(gl_apply(&d,&a,3)==GL_DUPLICATE && !d.consent);
    b.argument=1; assert(gl_apply(&d,&b,4)==GL_DUPLICATE && !d.consent);
}
TEST(revoke_with_reused_request_id_is_still_applied) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true);
    gl_command allow=cmd(GL_CONSENT,10,1), revoke=cmd(GL_CONSENT,10,0), cancel=cmd(GL_CANCEL,10,0);
    assert(gl_apply(&d,&allow,1)==GL_OK && d.consent);
    assert(gl_apply(&d,&revoke,2)==GL_OK && !d.consent);
    d.consent=true; gl_button(&d,false,3);
    assert(gl_apply(&d,&cancel,4)==GL_OK && !d.capture_requested);
}
TEST(queued_consent_before_revocation_cannot_restore_permission) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true);
    uint32_t queued_epoch=d.epoch; gl_command allow=cmd(GL_CONSENT,10,1);
    gl_button(&d,true,1);
    assert(gl_apply_at_epoch(&d,&allow,queued_epoch,2)==GL_STALE_EVENT && !d.consent);
    assert(gl_apply_at_epoch(&d,&allow,d.epoch,3)==GL_OK && d.consent);
}
TEST(status_query_does_not_consume_request_id) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true);
    gl_command c=cmd(GL_STATUS,1,0); assert(gl_apply(&d,&c,1)==GL_OK);
    c=cmd(GL_CONSENT,1,1); assert(gl_apply(&d,&c,2)==GL_OK);
}
TEST(disconnect_clears_consent_pending_capture_and_dedupe) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true); d.consent=true; assert(gl_button(&d,false,1)==GL_OK);
    gl_connected(&d,false); assert(!d.consent && !d.capture_requested && !d.connected && d.recent_count==0);
    gl_capture_finished(&d,true,2); assert(d.captures==0);
}
TEST(reconnect_cannot_reuse_old_consent) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true); d.consent=true;
    gl_connected(&d,true); assert(!d.consent && !d.capture_requested);
}
TEST(long_press_revokes_consent_and_cancels) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true); d.consent=true;
    assert(gl_button(&d,false,1)==GL_OK); assert(gl_button(&d,true,2)==GL_OK);
    assert(!d.consent && !d.capture_requested && d.state==GL_IDLE);
}
TEST(cancel_blocks_late_capture_result) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true); d.consent=true; gl_button(&d,false,1);
    gl_command c=cmd(GL_CANCEL,1,0); assert(gl_apply(&d,&c,2)==GL_OK);
    gl_capture_finished(&d,true,3); assert(d.captures==0);
}
TEST(capture_completion_does_not_claim_media_upload) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true); d.consent=true; gl_button(&d,false,1);
    gl_capture_finished(&d,true,2); assert(d.captures==1 && d.last_error==GL_MEDIA_NOT_CONFIGURED);
    assert(!d.capture_requested && d.state==GL_ERROR);
}
TEST(camera_failure_is_explicit) {
    gl_device d; gl_init(&d,true,true); gl_connected(&d,true); d.consent=true; gl_button(&d,false,1);
    gl_capture_finished(&d,false,2); assert(d.captures==0 && d.last_error==GL_CAMERA_FAILED);
}
TEST(error_ring_bounded_chronological_and_clearable) {
    gl_device d; gl_init(&d,false,false);
    for (unsigned i=0;i<20;i++) { d.request_id=(uint16_t)i; gl_error_push(&d,GL_BOARD_MISSING,i); }
    assert(d.log_count==16 && d.errors==20); gl_error_record r;
    assert(gl_error_get(&d,0,&r) && r.uptime_ms==4); assert(gl_error_get(&d,15,&r) && r.uptime_ms==19);
    assert(!gl_error_get(&d,16,&r)); gl_connected(&d,true); gl_command c=cmd(GL_CLEAR_LOG,20,0);
    assert(gl_apply(&d,&c,21)==GL_OK && d.log_count==0 && d.errors==20);
}
TEST(status_20_bytes_unknown_battery_and_no_false_privacy_flag) {
    gl_device d; gl_init(&d,true,false); gl_connected(&d,true); d.consent=true;
    d.request_id=0x1234; d.captures=7; d.errors=2; uint8_t bytes[20]; gl_encode_status(&d,0x12345678,bytes);
    assert(bytes[0]==1 && bytes[2]==7 && bytes[6]==255);
    assert(bytes[4]==0x34 && bytes[5]==0x12 && bytes[8]==0x78 && bytes[11]==0x12 && bytes[12]==7 && bytes[16]==2);
}
TEST(decoder_fuzz_lengths_and_bytes_stays_bounded) {
    uint8_t bytes[32]={0}; gl_command c;
    for (unsigned version=0;version<256;version++) for (unsigned op=0;op<256;op++) {
        bytes[0]=(uint8_t)version; bytes[1]=(uint8_t)op;
        for (size_t size=0;size<sizeof(bytes);size++) {
            bool ok=gl_decode_command(bytes,size,&c);
            assert(ok==(version==1 && op>=1 && op<=5 && size==8));
        }
    }
}
static bool fake_sink(const uint8_t *pixels, size_t bytes, uint16_t w, uint16_t h, void *context) {
    (void)pixels; (void)bytes; (void)w; (void)h; (*(unsigned *)context)++; return true;
}
TEST(display_unconfigured_or_unreviewed_never_calls_sink) {
    unsigned calls=0; uint8_t pixels[1]={0};
    gl_display_adapter none={0}, unreviewed={false,fake_sink,&calls};
    assert(gl_display_bitmap(&none,pixels,1,8,1)==GL_DISPLAY_UNCONFIGURED);
    assert(gl_display_bitmap(&unreviewed,pixels,1,8,1)==GL_DISPLAY_UNCONFIGURED && calls==0);
}
TEST(display_rejects_bad_bitmap_and_accepts_exact_buffer_contract) {
    unsigned calls=0; uint8_t pixels[2]={0}; gl_display_adapter fake={true,fake_sink,&calls};
    assert(gl_display_bitmap(&fake,pixels,2,8,1)==GL_DISPLAY_INVALID_BITMAP);
    assert(gl_display_bitmap(&fake,pixels,2,257,1)==GL_DISPLAY_INVALID_BITMAP);
    assert(gl_display_bitmap(&fake,NULL,1,8,1)==GL_DISPLAY_INVALID_BITMAP && calls==0);
    assert(gl_display_bitmap(&fake,pixels,2,9,1)==GL_DISPLAY_OK && calls==1);
}
int main(void) {
    RUN(protocol_valid_little_endian); RUN(protocol_rejects_bad_version_length_opcode_argument);
    RUN(unconfigured_never_captures); RUN(privacy_unverified_never_captures); RUN(capture_requires_connection_and_consent);
    RUN(replay_after_another_command_cannot_reapply_consent); RUN(status_query_does_not_consume_request_id);
    RUN(revoke_with_reused_request_id_is_still_applied); RUN(queued_consent_before_revocation_cannot_restore_permission);
    RUN(disconnect_clears_consent_pending_capture_and_dedupe); RUN(reconnect_cannot_reuse_old_consent);
    RUN(long_press_revokes_consent_and_cancels); RUN(cancel_blocks_late_capture_result);
    RUN(capture_completion_does_not_claim_media_upload); RUN(camera_failure_is_explicit);
    RUN(error_ring_bounded_chronological_and_clearable); RUN(status_20_bytes_unknown_battery_and_no_false_privacy_flag);
    RUN(decoder_fuzz_lengths_and_bytes_stays_bounded);
    RUN(display_unconfigured_or_unreviewed_never_calls_sink); RUN(display_rejects_bad_bitmap_and_accepts_exact_buffer_contract);
    printf("%u/%u host firmware tests passed (no hardware)\n",tests,tests); return 0;
}
