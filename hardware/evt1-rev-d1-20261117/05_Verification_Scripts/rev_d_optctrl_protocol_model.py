#!/usr/bin/env python3
"""Rev D independent behavioural model of the OPT_CTRL / RAW-window protocol.

This is NOT a substitute for iverilog. It re-implements, in Python, the exact
register-transfer semantics written in evt1_ar_display_fpga_bridge_rev_c.v for the
host_sck domain (nibble decode) and the host_cs_n-rising domain (RAW window), and checks
the protocol properties the Rev D testbench asserts. Purpose: catch logic-design errors
before CI runs the real simulation.
"""
import sys

class Bridge:
    def __init__(self):
        self.h_nib_cnt = 0; self.h_cmd_reg = 0; self.h_cmd_ok_q = 0; self.h_ctrl_ok_q = 0
        self.opt_scan_en_h = 0; self.opt_pwr_off_h = 0
        self.raw_req_tgl_h = 0; self.raw_ack_tgl_c = 0; self.raw_window_q = 0
        self.fb_words = 0  # counts framebuffer-word acceptances (h_cmd_ok at nibble 9)

    def sck_rise(self, qio):
        n = self.h_nib_cnt; nxt = {}
        if n == 0: nxt['h_cmd_reg'] = (qio << 4) | (self.h_cmd_reg & 0xF)
        elif n == 1: nxt['h_cmd_reg'] = (self.h_cmd_reg & 0xF0) | qio
        elif n == 2:
            nxt['h_cmd_ok_q'] = int((self.h_cmd_reg >> 2) == 0b101000 and not self.raw_window_q)
            nxt['h_ctrl_ok_q'] = int(self.h_cmd_reg == 0xA4 and not self.raw_window_q)
        elif n == 9:
            if self.h_cmd_ok_q: self.fb_words += 1
            if self.h_ctrl_ok_q:
                nxt['h_ctrl_ok_q'] = 0
                nxt['opt_scan_en_h'] = qio & 1
                nxt['opt_pwr_off_h'] = int(not (qio >> 1) & 1)
                if (qio >> 2) & 1 and not (qio & 1) and not self.opt_scan_en_h:
                    nxt['raw_req_tgl_h'] = self.raw_req_tgl_h ^ 1
        nxt['h_nib_cnt'] = 6 if n == 9 else n + 1
        for k, v in nxt.items(): setattr(self, k, v)   # non-blocking commit

    def cs_rise(self):
        w = int(self.raw_req_tgl_h != self.raw_ack_tgl_c); a = self.raw_req_tgl_h
        self.raw_window_q, self.raw_ack_tgl_c = w, a
        self.h_nib_cnt = 0                               # async reset on posedge host_cs_n

    def txn(self, nibbles):
        """Returns list of (mirrored?) flags observed on optics during this transaction."""
        mirrored = self.raw_window_q
        for q in nibbles: self.sck_rise(q)
        self.cs_rise()
        return mirrored

def ctrl(b, bits): return b.txn([0xA, 0x4, 0, 0, 0, 0, 0, 0, 0, bits])

def main():
    errs = []
    b = Bridge()
    # power-up defaults
    if b.opt_scan_en_h or b.opt_pwr_off_h or b.raw_window_q: errs.append("bad power-up defaults")
    # framebuffer write still decoded (0xA0, 1 word)
    b.txn([0xA, 0x0, 0, 0, 0, 0, 1, 2, 3, 4])
    if b.fb_words != 1: errs.append("0xA0 single word not accepted")
    # enable scan + power
    ctrl(b, 0b0011)
    if (b.opt_scan_en_h, b.opt_pwr_off_h) != (1, 0): errs.append("OPT_CTRL 0011 not applied")
    # power-off request
    ctrl(b, 0b0001)
    if b.opt_pwr_off_h != 1: errs.append("OPT_PWR_REQ=0 not applied")
    ctrl(b, 0b0011)
    # RAW_ARM while scan enabled -> rejected
    ctrl(b, 0b0111)
    if b.raw_window_q: errs.append("RAW_ARM accepted while SCAN_EN=1")
    # RAW_ARM in same write that clears SCAN_EN -> rejected (needs prior SCAN_EN=0)
    ctrl(b, 0b0110)
    if b.raw_window_q: errs.append("RAW_ARM accepted in same write that disabled scan")
    # now SCAN_EN==0 from previous write -> arm accepted
    ctrl(b, 0b0110)
    if not b.raw_window_q: errs.append("RAW_ARM not accepted with SCAN_EN already 0")
    fb_before = b.fb_words; scan_before = b.opt_scan_en_h
    m = b.txn([0xA, 0x0, 0, 0, 0, 0, 1, 2, 3, 4])     # raw payload starting with 0xA0
    if not m: errs.append("RAW transaction not mirrored")
    if b.fb_words != fb_before: errs.append("0xA0 decoded inside RAW window")
    if b.raw_window_q: errs.append("RAW window did not close after one transaction")
    m2 = ctrl(b, 0b0010)
    if m2: errs.append("transaction after RAW window was mirrored")
    # RAW payload that looks like OPT_CTRL must not change control state
    ctrl(b, 0b0110); scan_b, pwr_b = b.opt_scan_en_h, b.opt_pwr_off_h
    b.txn([0xA, 0x4, 0, 0, 0, 0, 0, 0, 0, 0b0001])
    if (b.opt_scan_en_h, b.opt_pwr_off_h) != (scan_b, pwr_b): errs.append("OPT_CTRL decoded inside RAW window")
    # multi-word OPT_CTRL applies only first word (no double toggle)
    tg = b.raw_req_tgl_h
    b.txn([0xA, 0x4, 0, 0, 0, 0, 0, 0, 0, 0b0110, 0, 0, 0, 0b0110])
    if b.raw_req_tgl_h == tg: errs.append("first word of multi-word OPT_CTRL ignored")
    if not b.raw_window_q: errs.append("multi-word OPT_CTRL double-toggled RAW request")
    b.txn([0] * 10)  # consume window
    print("OPTCTRL_MODEL_RESULT:", "PASS" if not errs else "FAIL", errs)
    return 0 if not errs else 1

if __name__ == "__main__":
    sys.exit(main())
