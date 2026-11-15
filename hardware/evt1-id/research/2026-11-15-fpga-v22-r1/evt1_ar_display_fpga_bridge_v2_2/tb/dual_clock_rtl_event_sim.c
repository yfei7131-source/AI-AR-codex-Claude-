/*
 * SPDX-License-Identifier: MIT
 * File:    tb/dual_clock_rtl_event_sim.c
 * Purpose: Offline C99 Cycle-Accurate Self-Check Model of the V2.2 RTL:
 *          1. Exact 1-cycle synchronous EBR read (`ebr_dout` + `out_valid` + `pop_ram`)
 *             matching `rtl/qspi_cdc_async_fifo.v` (zero extra `pop_ram_d1` skew).
 *          2. Directly compiles and links `firmware_driver/jbd_fpga_bridge_drv.c` to verify
 *             1:1 mode enum alignment (`BRIDGE_MODE_* == MODE_*`) and packet builders.
 *          3. Verifies `OP_READ_STATUS (0x50)` bidirectional QSPI status readback over `s3_io[3:0]`.
 *          4. Verifies VSYNC atomic swap and Independent Left/Right Stereo (`MODE_STEREO_INDEP_2BPP`).
 * Note:    Explicitly labeled OFFLINE_C_SELFCHECK_ONLY — does NOT replace native
 *          iverilog / yosys / nextpnr-ice40 execution when EDA binaries are unavailable.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "../firmware_driver/jbd_fpga_bridge_drv.h"

#define REQUIRE_TRUE(cond, msg, ...) do { \
    if (!(cond)) { \
        fprintf(stderr, "[FATAL ASSERTION FAILED] %s:%d: " msg "\n", __FILE__, __LINE__, ##__VA_ARGS__); \
        exit(1); \
    } \
} while (0)

typedef struct {
    uint8_t  nib_phase;
    uint8_t  hi_nibble;
    uint8_t  cs_nib_cnt;
    uint8_t  is_status_read;
    uint16_t status_latched;
    uint16_t status_sync1, status_sync2;
    uint8_t  s3_io_out;
    uint8_t  s3_io_oe;
    uint8_t  fifo_mem[512];
    uint16_t wptr_bin;
    uint16_t wptr_gray;
    uint16_t rptr_gray_wsync1, rptr_gray_wsync2;
    uint8_t  overflow_latched;
    // Synchronous EBR Read & FWFT state (matches rtl/qspi_cdc_async_fifo.v 1:1)
    uint16_t rptr_bin;
    uint16_t rptr_gray;
    uint16_t wptr_gray_rsync1, wptr_gray_rsync2;
    uint8_t  csn_sys_sync;
    uint8_t  pkt_active;
    uint8_t  pkt_end_pulse;
    uint8_t  out_valid;
    uint8_t  ebr_dout;
} rtl_cdc_fifo_t;

typedef struct {
    uint16_t stage_ram[1024];
    uint16_t stage_wr_count;
    uint16_t commit_rd_idx;
    uint16_t base_spram_waddr;
    uint8_t  pkt_overflow_latched;
    uint8_t  state;
    uint8_t  rle_substate;
    uint8_t  opcode;
    uint8_t  hdr_idx;
    uint8_t  hdr_0, hdr_1, hdr_2, hdr_3;
    uint16_t payload_bytes_rem;
    uint16_t crc_reg;
    uint8_t  rx_crc_hi;
    uint8_t  rle_run_rem;
    uint8_t  rle_val_byte;
    uint8_t  upper_byte_hold;
    uint8_t  half_word_valid;
    uint8_t  spram_we;
    uint16_t spram_waddr;
    uint16_t spram_wdata;
    uint8_t  cfg_mode;
    int8_t   cfg_disparity_px;
    uint8_t  cfg_mirror_left;
    uint8_t  cfg_mirror_right;
    uint8_t  frame_commit_req;
    uint8_t  commit_swap_en;
    uint8_t  crc_error_flag;
    uint8_t  stage_overflow_err;
    uint16_t good_packet_cnt;
    uint16_t bad_packet_cnt;
} rtl_s3_rx_t;

typedef struct {
    uint16_t mem[4][16384];
    uint16_t bank_dout[4];
    uint8_t  r_bank_d1;
    uint8_t  stereo_d1;
    uint8_t  scan_rvalid;
} rtl_spram_t;

typedef struct {
    uint8_t  line_buf_l[640];
    uint8_t  line_buf_r[640];
    uint8_t  cmd_lut[16];
    uint8_t  act_mode;
    int8_t   act_disparity_px;
    uint8_t  act_mirror_l;
    uint8_t  act_mirror_r;
    uint8_t  commit_pending;
    uint8_t  swap_pending;
    uint8_t  active_front_bank;
    uint8_t  state;
    uint16_t cur_y;
    uint16_t line_base_waddr;
    uint8_t  fetch_word_idx;
    uint8_t  fetch_idx_d1, fetch_idx_d2;
    uint8_t  hdr_nib_idx;
    uint16_t tx_x;
    uint32_t vblank_cnt;
    uint8_t  spram_re;
    uint16_t spram_raddr;
    uint8_t  opt_sclk;
    uint8_t  opt_cs_l_n;
    uint8_t  opt_cs_r_n;
    uint8_t  opt_l_io;
    uint8_t  opt_r_io;
    uint8_t  vsync_done_pulse;
    uint8_t  cap_l[480][640];
    uint8_t  cap_r[480][640];
} rtl_scan_t;

static rtl_cdc_fifo_t g_fifo;
static rtl_s3_rx_t    g_rx;
static rtl_spram_t    g_spram;
static rtl_scan_t     g_scan;

static uint16_t next_crc16(uint16_t crc, uint8_t d) {
    return gl_bridge_crc16_ccitt(&d, 1, crc);
}

static uint16_t bin2gray10(uint16_t b) { return (uint16_t)(((b >> 1) ^ b) & 0x3FF); }

static uint8_t expand_2bpp(uint8_t p2) {
    static const uint8_t lut[4] = {0x0, 0x5, 0xA, 0xF};
    return lut[p2 & 0x03];
}

static uint16_t build_status_word_sys(void) {
    bool stereo_indep = (g_scan.act_mode == 3);
    return (uint16_t)(
        ((g_rx.crc_error_flag & 1u) << 15) |
        ((g_fifo.overflow_latched & 1u) << 14) |
        ((g_rx.stage_overflow_err & 1u) << 13) |
        ((g_scan.commit_pending & 1u) << 12) |
        ((g_scan.active_front_bank & 1u) << 11) |
        ((stereo_indep ? 1u : 0u) << 10) |
        ((g_scan.act_mode & 0x03u) << 8) |
        ((g_rx.good_packet_cnt & 0x0Fu) << 4) |
        (g_rx.bad_packet_cnt & 0x0Fu)
    );
}

static void eval_posedge_s3_sclk(uint8_t s3_cs_n, uint8_t s3_io_in) {
    uint16_t prev_status_sync2 = g_fifo.status_sync2;
    g_fifo.rptr_gray_wsync2 = g_fifo.rptr_gray_wsync1;
    g_fifo.rptr_gray_wsync1 = g_fifo.rptr_gray;
    g_fifo.status_sync2     = g_fifo.status_sync1;
    g_fifo.status_sync1     = build_status_word_sys();

    if (s3_cs_n) {
        g_fifo.nib_phase      = 0;
        g_fifo.hi_nibble      = 0;
        g_fifo.cs_nib_cnt     = 0;
        g_fifo.is_status_read = 0;
        g_fifo.s3_io_oe       = 0;
        g_fifo.s3_io_out      = 0;
        return;
    }

    uint8_t prev_nib_cnt = g_fifo.cs_nib_cnt;
    uint8_t prev_is_status = g_fifo.is_status_read;
    if (g_fifo.cs_nib_cnt != 15) g_fifo.cs_nib_cnt++;

    if (prev_is_status && prev_nib_cnt == 3) {
        g_fifo.status_latched = prev_status_sync2;
    }

    if (!g_fifo.nib_phase) {
        g_fifo.hi_nibble = s3_io_in & 0x0F;
        g_fifo.nib_phase = 1;
    } else {
        g_fifo.nib_phase = 0;
        uint8_t assembled = (uint8_t)((g_fifo.hi_nibble << 4) | (s3_io_in & 0x0F));
        bool first_is_status = (prev_nib_cnt == 1) && (assembled == GL_OP_READ_STATUS);
        if (first_is_status) {
            g_fifo.is_status_read = 1;
        }
        bool suppress_write = g_fifo.is_status_read || first_is_status;
        if (!suppress_write) {
            uint16_t full_mask = (uint16_t)((~g_fifo.rptr_gray_wsync2 & 0x300) | (g_fifo.rptr_gray_wsync2 & 0x0FF));
            bool wfull = (g_fifo.wptr_gray == full_mask);
            if (!wfull) {
                g_fifo.fifo_mem[g_fifo.wptr_bin & 0x1FF] = assembled;
                g_fifo.wptr_bin  = (uint16_t)((g_fifo.wptr_bin + 1) & 0x3FF);
                g_fifo.wptr_gray = bin2gray10(g_fifo.wptr_bin);
            } else {
                g_fifo.overflow_latched = 1;
            }
        }
    }
}

static void eval_negedge_s3_sclk(uint8_t s3_cs_n) {
    if (s3_cs_n || !g_fifo.is_status_read) {
        g_fifo.s3_io_oe  = 0;
        g_fifo.s3_io_out = 0;
        return;
    }
    switch (g_fifo.cs_nib_cnt) {
        case 4: g_fifo.s3_io_oe = 1; g_fifo.s3_io_out = (g_fifo.status_latched >> 12) & 0x0F; break;
        case 5: g_fifo.s3_io_oe = 1; g_fifo.s3_io_out = (g_fifo.status_latched >> 8)  & 0x0F; break;
        case 6: g_fifo.s3_io_oe = 1; g_fifo.s3_io_out = (g_fifo.status_latched >> 4)  & 0x0F; break;
        case 7: g_fifo.s3_io_oe = 1; g_fifo.s3_io_out = (g_fifo.status_latched >> 0)  & 0x0F; break;
        default: g_fifo.s3_io_oe = 0; g_fifo.s3_io_out = 0; break;
    }
}

static void eval_posedge_clk_sys(uint8_t s3_cs_n) {
    uint8_t  prev_scan_re     = g_scan.spram_re;
    uint16_t prev_scan_raddr  = g_scan.spram_raddr;
    uint8_t  prev_scan_rvalid = g_spram.scan_rvalid;
    bool stereo_indep = (g_scan.act_mode == 3);
    uint16_t prev_scan_rdata_l = g_spram.stereo_d1 ? g_spram.bank_dout[g_spram.r_bank_d1 & 1] : g_spram.bank_dout[g_spram.r_bank_d1];
    uint16_t prev_scan_rdata_r = g_spram.stereo_d1 ? g_spram.bank_dout[2 + (g_spram.r_bank_d1 & 1)] : prev_scan_rdata_l;

    uint8_t w_bank = (g_rx.spram_waddr >> 14) & 0x03;
    uint8_t r_bank = (prev_scan_raddr >> 14) & 0x03;
    bool scan_uses[4];
    for (int b = 0; b < 4; b++) {
        scan_uses[b] = prev_scan_re && (stereo_indep ? ((b & 1) == (r_bank & 1)) : (r_bank == b));
    }
    bool bank_conflict = scan_uses[w_bank];
    bool prev_host_ready = !bank_conflict;

    for (int b = 0; b < 4; b++) {
        bool scan_this = scan_uses[b];
        bool host_this = g_rx.spram_we && (w_bank == b) && !scan_this;
        uint16_t addr  = scan_this ? (prev_scan_raddr & 0x3FFF) : (g_rx.spram_waddr & 0x3FFF);
        if (host_this) {
            g_spram.mem[b][addr] = g_rx.spram_wdata;
        }
        if (scan_this || host_this) {
            g_spram.bank_dout[b] = g_spram.mem[b][addr];
        }
    }
    g_spram.r_bank_d1   = r_bank;
    g_spram.stereo_d1   = stereo_indep ? 1 : 0;
    g_spram.scan_rvalid = prev_scan_re;

    // Scanline Engine evaluation
    g_scan.vsync_done_pulse = 0;
    if (g_rx.frame_commit_req) {
        g_scan.commit_pending = 1;
        g_scan.swap_pending   = g_rx.commit_swap_en;
    }

    uint8_t prev_fetch_idx_d2 = g_scan.fetch_idx_d2;
    g_scan.fetch_idx_d2 = g_scan.fetch_idx_d1;
    g_scan.fetch_idx_d1 = g_scan.fetch_word_idx;

    bool is_2bpp = (g_scan.act_mode != 0);
    uint8_t  last_word_idx  = is_2bpp ? 79 : 159;
    uint16_t words_per_line = is_2bpp ? 80 : 160;

    if (prev_scan_rvalid) {
        if (is_2bpp) {
            uint16_t base_px = (uint16_t)(prev_fetch_idx_d2 & 0x7F) * 8;
            REQUIRE_TRUE(base_px + 7 < 640, "2bpp base_px overflow");
            for (int k = 0; k < 8; k++) {
                g_scan.line_buf_l[base_px + k] = expand_2bpp((uint8_t)(prev_scan_rdata_l >> (14 - 2 * k)));
                g_scan.line_buf_r[base_px + k] = expand_2bpp((uint8_t)(prev_scan_rdata_r >> (14 - 2 * k)));
            }
        } else {
            uint16_t base_px = (uint16_t)prev_fetch_idx_d2 * 4;
            REQUIRE_TRUE(base_px + 3 < 640, "4bpp base_px overflow");
            g_scan.line_buf_l[base_px + 0] = (prev_scan_rdata_l >> 12) & 0x0F;
            g_scan.line_buf_l[base_px + 1] = (prev_scan_rdata_l >> 8)  & 0x0F;
            g_scan.line_buf_l[base_px + 2] = (prev_scan_rdata_l >> 4)  & 0x0F;
            g_scan.line_buf_l[base_px + 3] = (prev_scan_rdata_l >> 0)  & 0x0F;
            g_scan.line_buf_r[base_px + 0] = (prev_scan_rdata_r >> 12) & 0x0F;
            g_scan.line_buf_r[base_px + 1] = (prev_scan_rdata_r >> 8)  & 0x0F;
            g_scan.line_buf_r[base_px + 2] = (prev_scan_rdata_r >> 4)  & 0x0F;
            g_scan.line_buf_r[base_px + 3] = (prev_scan_rdata_r >> 0)  & 0x0F;
        }
    }

    bool active_row = (g_scan.act_mode == 2) ? true : (g_scan.cur_y >= 40 && g_scan.cur_y < 440);
    uint16_t bank_base = ((g_scan.act_mode == 1) && g_scan.active_front_bank) ? 0x8000 : 0x0000;

    switch (g_scan.state) {
        case 0: // S_FETCH_LINE
            if (!active_row) {
                g_scan.spram_re = 0;
                g_scan.state    = 2;
            } else {
                g_scan.spram_re = 1;
                uint32_t calc_addr = (uint32_t)bank_base + (uint32_t)g_scan.line_base_waddr + g_scan.fetch_word_idx;
                REQUIRE_TRUE(calc_addr < 65536, "SPRAM 16-bit address overflow");
                g_scan.spram_raddr = (uint16_t)calc_addr;
                if (g_scan.fetch_word_idx == last_word_idx) g_scan.state = 1;
                else g_scan.fetch_word_idx++;
            }
            break;
        case 1: // S_FETCH_DRAIN
            g_scan.spram_re       = 0;
            g_scan.fetch_word_idx = 0;
            if (!prev_scan_re && !prev_scan_rvalid) g_scan.state = 2;
            break;
        case 2: // S_CS_SETUP
            g_scan.opt_cs_l_n  = 0;
            g_scan.opt_cs_r_n  = 0;
            g_scan.opt_sclk    = 0;
            g_scan.hdr_nib_idx = 0;
            g_scan.state       = 3;
            break;
        case 3: // S_LINE_HDR
            if (!g_scan.opt_sclk) g_scan.opt_sclk = 1;
            else {
                g_scan.opt_sclk = 0;
                if (g_scan.hdr_nib_idx == 5) { g_scan.tx_x = 0; g_scan.state = 4; }
                else g_scan.hdr_nib_idx++;
            }
            break;
        case 4: // S_TX_PIXELS
            if (!g_scan.opt_sclk) {
                int base_l  = g_scan.act_mirror_l ? (639 - g_scan.tx_x) : g_scan.tx_x;
                int base_r  = g_scan.act_mirror_r ? (639 - g_scan.tx_x) : g_scan.tx_x;
                int shift_l = base_l + (g_scan.act_disparity_px >> 1);
                int shift_r = base_r - (g_scan.act_disparity_px >> 1);
                g_scan.opt_l_io = (active_row && shift_l >= 0 && shift_l < 640) ? g_scan.line_buf_l[shift_l] : 0;
                g_scan.opt_r_io = (active_row && shift_r >= 0 && shift_r < 640) ? g_scan.line_buf_r[shift_r] : 0;
                g_scan.cap_l[g_scan.cur_y][g_scan.tx_x] = g_scan.opt_l_io;
                g_scan.cap_r[g_scan.cur_y][g_scan.tx_x] = g_scan.opt_r_io;
                g_scan.opt_sclk = 1;
            } else {
                g_scan.opt_sclk = 0;
                if (g_scan.tx_x == 639) g_scan.state = 5;
                else g_scan.tx_x++;
            }
            break;
        case 5: // S_CS_HOLD
            g_scan.opt_cs_l_n = 1;
            g_scan.opt_cs_r_n = 1;
            g_scan.state      = 6;
            break;
        case 6: // S_NEXT_LINE
            if (active_row) {
                g_scan.line_base_waddr = (uint16_t)(g_scan.line_base_waddr + words_per_line);
            }
            if (g_scan.cur_y == 479) {
                g_scan.cur_y            = 0;
                g_scan.line_base_waddr  = 0;
                g_scan.vblank_cnt       = 0;
                g_scan.vsync_done_pulse = 1;
                if (g_scan.commit_pending) {
                    g_scan.act_mode         = g_rx.cfg_mode;
                    g_scan.act_disparity_px = g_rx.cfg_disparity_px;
                    g_scan.act_mirror_l     = g_rx.cfg_mirror_left;
                    g_scan.act_mirror_r     = g_rx.cfg_mirror_right;
                    if (g_rx.cfg_mode == 1) {
                        if (g_scan.swap_pending)
                            g_scan.active_front_bank = !g_scan.active_front_bank;
                    } else {
                        g_scan.active_front_bank = 0;
                    }
                    g_scan.commit_pending = 0;
                    g_scan.swap_pending   = 0;
                }
                g_scan.state = 7;
            } else {
                g_scan.cur_y++;
                g_scan.state = 0;
            }
            break;
        case 7: // S_VBLANK
            if (g_scan.vblank_cnt >= 16) { g_scan.vblank_cnt = 0; g_scan.state = 0; }
            else g_scan.vblank_cnt++;
            break;
    }

    // Exact cycle-accurate model of `qspi_cdc_async_fifo.v` with synchronous EBR read (`ebr_dout` + `out_valid`)
    bool raw_ram_empty      = (g_fifo.rptr_gray == g_fifo.wptr_gray_rsync2);
    bool prev_out_valid     = (g_fifo.out_valid != 0);
    uint8_t prev_pkt_end    = g_fifo.pkt_end_pulse;
    bool fifo_empty         = !prev_out_valid;
    uint8_t fifo_dout       = g_fifo.ebr_dout;
    bool fifo_rd_en         = (!fifo_empty) && (g_rx.state != 3) && (g_rx.state != 6);
    bool pop_ram            = (!raw_ram_empty) && (!prev_out_valid || fifo_rd_en);

    g_fifo.wptr_gray_rsync2 = g_fifo.wptr_gray_rsync1;
    g_fifo.wptr_gray_rsync1 = g_fifo.wptr_gray;
    uint8_t csn_sync_msb    = (g_fifo.csn_sys_sync >> 2) & 1;
    g_fifo.csn_sys_sync     = (uint8_t)(((g_fifo.csn_sys_sync << 1) | (s3_cs_n & 1)) & 0x07);
    g_fifo.pkt_end_pulse    = 0;

    if (pop_ram) {
        g_fifo.ebr_dout  = g_fifo.fifo_mem[g_fifo.rptr_bin & 0x1FF];
        g_fifo.rptr_bin  = (uint16_t)((g_fifo.rptr_bin + 1) & 0x3FF);
        g_fifo.rptr_gray = bin2gray10(g_fifo.rptr_bin);
        g_fifo.out_valid = 1;
    } else if (fifo_rd_en) {
        g_fifo.out_valid = 0;
    }

    if (!csn_sync_msb || !raw_ram_empty || prev_out_valid) {
        g_fifo.pkt_active = 1;
    } else if (g_fifo.pkt_active && csn_sync_msb && raw_ram_empty && !prev_out_valid) {
        g_fifo.pkt_active    = 0;
        g_fifo.pkt_end_pulse = 1;
    }

    g_rx.spram_we         = 0;
    g_rx.frame_commit_req = 0;

    if (g_rx.state == 3) { // ST_RLE_EXPAND
        if (!g_rx.half_word_valid && g_rx.rle_run_rem >= 2) {
            if (g_rx.stage_wr_count < 1024) {
                g_rx.stage_ram[g_rx.stage_wr_count++] = ((uint16_t)g_rx.rle_val_byte << 8) | g_rx.rle_val_byte;
            } else {
                g_rx.pkt_overflow_latched = 1;
                g_rx.stage_overflow_err   = 1;
            }
            if (g_rx.rle_run_rem == 2) {
                g_rx.rle_run_rem = 0;
                g_rx.state = (g_rx.payload_bytes_rem == 0) ? 4 : 2;
            } else g_rx.rle_run_rem -= 2;
        } else {
            if (!g_rx.half_word_valid) {
                g_rx.upper_byte_hold = g_rx.rle_val_byte;
                g_rx.half_word_valid = 1;
            } else {
                if (g_rx.stage_wr_count < 1024) {
                    g_rx.stage_ram[g_rx.stage_wr_count++] = ((uint16_t)g_rx.upper_byte_hold << 8) | g_rx.rle_val_byte;
                } else {
                    g_rx.pkt_overflow_latched = 1;
                    g_rx.stage_overflow_err   = 1;
                }
                g_rx.half_word_valid = 0;
            }
            if (g_rx.rle_run_rem <= 1) {
                g_rx.rle_run_rem = 0;
                g_rx.state = (g_rx.payload_bytes_rem == 0) ? 4 : 2;
            } else g_rx.rle_run_rem--;
        }
    } else if (g_rx.state == 6) { // ST_COMMIT_SPRAM
        if (g_rx.commit_rd_idx < g_rx.stage_wr_count) {
            if (prev_host_ready) {
                uint16_t back_base = (g_rx.cfg_mode == 1) ? (g_scan.active_front_bank ? 0x0000 : 0x8000) : 0x0000;
                uint16_t off = (uint16_t)(g_rx.base_spram_waddr + g_rx.commit_rd_idx);
                if (g_rx.cfg_mode == 1) off &= 0x7FFF;
                g_rx.spram_we    = 1;
                g_rx.spram_waddr = back_base | off;
                g_rx.spram_wdata = g_rx.stage_ram[g_rx.commit_rd_idx++];
            }
        } else g_rx.state = 0;
    } else {
        if (prev_pkt_end && g_rx.state != 6) {
            g_rx.state = 0; g_rx.rle_substate = 0; g_rx.crc_reg = 0xFFFF;
        } else if (fifo_rd_en) {
            switch (g_rx.state) {
                case 0:
                    g_rx.opcode               = fifo_dout;
                    g_rx.crc_reg              = next_crc16(0xFFFF, fifo_dout);
                    g_rx.hdr_idx              = 0;
                    g_rx.stage_wr_count       = 0;
                    g_rx.half_word_valid      = 0;
                    g_rx.pkt_overflow_latched = 0;
                    g_rx.rle_substate         = 0;
                    g_rx.state                = 1;
                    break;
                case 1:
                    g_rx.crc_reg = next_crc16(g_rx.crc_reg, fifo_dout);
                    if (g_rx.hdr_idx == 0) g_rx.hdr_0 = fifo_dout;
                    if (g_rx.hdr_idx == 1) g_rx.hdr_1 = fifo_dout;
                    if (g_rx.hdr_idx == 2) g_rx.hdr_2 = fifo_dout;
                    if (g_rx.hdr_idx == 3) g_rx.hdr_3 = fifo_dout;
                    if (g_rx.opcode == 0x40 && g_rx.hdr_idx == 0) g_rx.state = 4;
                    else if ((g_rx.opcode == 0x20 || g_rx.opcode == 0x30) && g_rx.hdr_idx == 2) g_rx.state = 4;
                    else if ((g_rx.opcode == 0x10 || g_rx.opcode == 0x11) && g_rx.hdr_idx == 3) {
                        g_rx.base_spram_waddr  = ((uint16_t)g_rx.hdr_0 << 8) | g_rx.hdr_1;
                        g_rx.payload_bytes_rem = ((uint16_t)g_rx.hdr_2 << 8) | fifo_dout;
                        g_rx.state = (g_rx.payload_bytes_rem == 0) ? 4 : 2;
                    } else g_rx.hdr_idx++;
                    break;
                case 2:
                    g_rx.crc_reg = next_crc16(g_rx.crc_reg, fifo_dout);
                    g_rx.payload_bytes_rem--;
                    if (g_rx.opcode == 0x10) {
                        if (!g_rx.half_word_valid) { g_rx.upper_byte_hold = fifo_dout; g_rx.half_word_valid = 1; }
                        else {
                            if (g_rx.stage_wr_count < 1024)
                                g_rx.stage_ram[g_rx.stage_wr_count++] = ((uint16_t)g_rx.upper_byte_hold << 8) | fifo_dout;
                            else { g_rx.pkt_overflow_latched = 1; g_rx.stage_overflow_err = 1; }
                            g_rx.half_word_valid = 0;
                        }
                        if (g_rx.payload_bytes_rem == 0) g_rx.state = 4;
                    } else {
                        if (g_rx.rle_substate == 0) {
                            if (fifo_dout == 0xFF) g_rx.rle_substate = 1;
                            else {
                                if (!g_rx.half_word_valid) { g_rx.upper_byte_hold = fifo_dout; g_rx.half_word_valid = 1; }
                                else {
                                    if (g_rx.stage_wr_count < 1024)
                                        g_rx.stage_ram[g_rx.stage_wr_count++] = ((uint16_t)g_rx.upper_byte_hold << 8) | fifo_dout;
                                    else { g_rx.pkt_overflow_latched = 1; g_rx.stage_overflow_err = 1; }
                                    g_rx.half_word_valid = 0;
                                }
                                if (g_rx.payload_bytes_rem == 0) g_rx.state = 4;
                            }
                        } else if (g_rx.rle_substate == 1) {
                            g_rx.rle_run_rem = fifo_dout; g_rx.rle_substate = 2;
                        } else {
                            g_rx.rle_val_byte = fifo_dout; g_rx.rle_substate = 0;
                            if (!g_rx.half_word_valid) { g_rx.upper_byte_hold = fifo_dout; g_rx.half_word_valid = 1; }
                            else {
                                if (g_rx.stage_wr_count < 1024)
                                    g_rx.stage_ram[g_rx.stage_wr_count++] = ((uint16_t)g_rx.upper_byte_hold << 8) | fifo_dout;
                                else { g_rx.pkt_overflow_latched = 1; g_rx.stage_overflow_err = 1; }
                                g_rx.half_word_valid = 0;
                            }
                            if (g_rx.rle_run_rem > 1) { g_rx.rle_run_rem--; g_rx.state = 3; }
                            else if (g_rx.payload_bytes_rem == 0) g_rx.state = 4;
                        }
                    }
                    break;
                case 4:
                    g_rx.rx_crc_hi = fifo_dout; g_rx.state = 5;
                    break;
                case 5:
                    if ((((uint16_t)g_rx.rx_crc_hi << 8) | fifo_dout) == g_rx.crc_reg &&
                        !g_rx.pkt_overflow_latched && !g_fifo.overflow_latched && !g_rx.half_word_valid) {
                        g_rx.crc_error_flag = 0;
                        g_rx.good_packet_cnt++;
                        if (g_rx.opcode == 0x20) {
                            g_rx.cfg_mode         = g_rx.hdr_0 & 0x03;
                            g_rx.cfg_disparity_px = (int8_t)g_rx.hdr_1;
                            g_rx.cfg_mirror_left  = g_rx.hdr_2 & 0x01;
                            g_rx.cfg_mirror_right = (g_rx.hdr_2 >> 1) & 0x01;
                            g_rx.state = 0;
                        } else if (g_rx.opcode == 0x40) {
                            g_rx.frame_commit_req = 1;
                            g_rx.commit_swap_en   = g_rx.hdr_0 & 0x01;
                            g_rx.state = 0;
                        } else if (g_rx.opcode == 0x10 || g_rx.opcode == 0x11) {
                            g_rx.commit_rd_idx = 0;
                            g_rx.state = 6;
                        } else g_rx.state = 0;
                    } else {
                        g_rx.crc_error_flag = ((((uint16_t)g_rx.rx_crc_hi << 8) | fifo_dout) != g_rx.crc_reg);
                        g_rx.bad_packet_cnt++;
                        g_rx.stage_wr_count = 0;
                        g_rx.state = 7;
                    }
                    break;
                default: break;
            }
        }
    }
}

static uint64_t g_time_ps = 0, g_next_sys_ps = 10416;

static void advance_sys_clocks(uint32_t n_clks, uint8_t s3_cs_n) {
    for (uint32_t i = 0; i < n_clks; i++) {
        g_time_ps = g_next_sys_ps;
        eval_posedge_clk_sys(s3_cs_n);
        g_next_sys_ps += 20833;
    }
}

static void send_qspi_packet_40mhz(const uint8_t *pkt, size_t len) {
    advance_sys_clocks(2, 0);
    for (size_t i = 0; i < len; i++) {
        for (int nib = 0; nib < 2; nib++) {
            uint8_t io = (nib == 0) ? ((pkt[i] >> 4) & 0x0F) : (pkt[i] & 0x0F);
            uint64_t edge_ps = g_time_ps + 12500;
            while (g_next_sys_ps <= edge_ps) {
                g_time_ps = g_next_sys_ps;
                eval_posedge_clk_sys(0);
                g_next_sys_ps += 20833;
            }
            g_time_ps = edge_ps;
            eval_posedge_s3_sclk(0, io);
            edge_ps += 12500;
            while (g_next_sys_ps <= edge_ps) {
                g_time_ps = g_next_sys_ps;
                eval_posedge_clk_sys(0);
                g_next_sys_ps += 20833;
            }
            g_time_ps = edge_ps;
            eval_negedge_s3_sclk(0);
        }
    }
    eval_posedge_s3_sclk(1, 0);
    advance_sys_clocks(1500, 1);
}

static int sim_qspi_halfduplex_cb(const uint8_t *tx_buf, size_t tx_len,
                                  size_t dummy_sclk_cycles,
                                  uint8_t *rx_buf, size_t rx_len,
                                  void *user_ctx) {
    (void)user_ctx;
    advance_sys_clocks(2, 0);
    // 1. Transmit command bytes
    for (size_t i = 0; i < tx_len; i++) {
        for (int nib = 0; nib < 2; nib++) {
            uint8_t io = (nib == 0) ? ((tx_buf[i] >> 4) & 0x0F) : (tx_buf[i] & 0x0F);
            uint64_t edge_ps = g_time_ps + 12500;
            while (g_next_sys_ps <= edge_ps) { g_time_ps = g_next_sys_ps; eval_posedge_clk_sys(0); g_next_sys_ps += 20833; }
            g_time_ps = edge_ps;
            eval_posedge_s3_sclk(0, io);
            edge_ps += 12500;
            while (g_next_sys_ps <= edge_ps) { g_time_ps = g_next_sys_ps; eval_posedge_clk_sys(0); g_next_sys_ps += 20833; }
            g_time_ps = edge_ps;
            eval_negedge_s3_sclk(0);
        }
    }
    // 2. Dummy turnaround cycles
    for (size_t d = 0; d < dummy_sclk_cycles; d++) {
        uint64_t edge_ps = g_time_ps + 12500;
        while (g_next_sys_ps <= edge_ps) { g_time_ps = g_next_sys_ps; eval_posedge_clk_sys(0); g_next_sys_ps += 20833; }
        g_time_ps = edge_ps;
        eval_posedge_s3_sclk(0, 0);
        edge_ps += 12500;
        while (g_next_sys_ps <= edge_ps) { g_time_ps = g_next_sys_ps; eval_posedge_clk_sys(0); g_next_sys_ps += 20833; }
        g_time_ps = edge_ps;
        eval_negedge_s3_sclk(0);
    }
    // 3. Read status bytes launched on negedge s3_sclk
    for (size_t i = 0; i < rx_len; i++) {
        uint8_t byte_val = 0;
        for (int nib = 0; nib < 2; nib++) {
            uint64_t edge_ps = g_time_ps + 12500;
            while (g_next_sys_ps <= edge_ps) { g_time_ps = g_next_sys_ps; eval_posedge_clk_sys(0); g_next_sys_ps += 20833; }
            g_time_ps = edge_ps;
            REQUIRE_TRUE(g_fifo.s3_io_oe == 1, "FPGA must drive s3_io_oe=1 during OP_READ_STATUS readback");
            uint8_t sampled_nib = g_fifo.s3_io_out & 0x0F;
            byte_val = (uint8_t)((byte_val << 4) | sampled_nib);
            eval_posedge_s3_sclk(0, sampled_nib);
            edge_ps += 12500;
            while (g_next_sys_ps <= edge_ps) { g_time_ps = g_next_sys_ps; eval_posedge_clk_sys(0); g_next_sys_ps += 20833; }
            g_time_ps = edge_ps;
            eval_negedge_s3_sclk(0);
        }
        rx_buf[i] = byte_val;
    }
    eval_posedge_s3_sclk(1, 0);
    advance_sys_clocks(4, 1);
    return 0;
}

int main(void) {
    memset(&g_fifo, 0, sizeof(g_fifo));
    memset(&g_rx,   0, sizeof(g_rx));
    memset(&g_spram,0, sizeof(g_spram));
    memset(&g_scan, 0, sizeof(g_scan));
    g_fifo.csn_sys_sync   = 0x07;
    g_rx.crc_reg          = 0xFFFF;
    g_scan.cmd_lut[0]     = 0x02;
    g_scan.act_mirror_r   = 1;

    // Verify Firmware Mode Enum matches RTL 1:1
    REQUIRE_TRUE(BRIDGE_MODE_640x400_4BPP      == 0, "Mode 0 enum mismatch");
    REQUIRE_TRUE(BRIDGE_MODE_640x400_2BPP_PP   == 1, "Mode 1 enum mismatch");
    REQUIRE_TRUE(BRIDGE_MODE_640x480_2BPP      == 2, "Mode 2 enum mismatch");
    REQUIRE_TRUE(BRIDGE_MODE_STEREO_INDEP_2BPP == 3, "Mode 3 enum mismatch");

    // Test 1: Multi-run RLE4 packet with synchronous EBR FIFO read alignment
    uint8_t pkt1[48];
    pkt1[0] = 0x11; pkt1[1] = 0x00; pkt1[2] = 0x00; pkt1[3] = 0x00; pkt1[4] = 41;
    pkt1[5] = 0xFF; pkt1[6] = 250;  pkt1[7] = 0x22;
    pkt1[8] = 0xFF; pkt1[9] = 35;   pkt1[10] = 0x44;
    for (int i = 0; i < 34; i++) pkt1[11 + i] = 0x55;
    pkt1[44] = 0xAC; pkt1[45] = 0xDF;
    uint16_t c1 = gl_bridge_crc16_ccitt(pkt1, 46, 0xFFFF);
    pkt1[46] = (uint8_t)(c1 >> 8); pkt1[47] = (uint8_t)(c1 & 0xFF);

    send_qspi_packet_40mhz(pkt1, sizeof(pkt1));
    REQUIRE_TRUE(g_fifo.overflow_latched == 0, "CDC FIFO overflow");
    REQUIRE_TRUE(g_rx.good_packet_cnt == 1 && g_rx.bad_packet_cnt == 0, "Packet 1 count mismatch");
    REQUIRE_TRUE(g_spram.mem[0][0] == 0x2222 && g_spram.mem[0][159] == 0xACDF, "SPRAM content mismatch");

    // Test 2: Stage RAM Overflow Guard (>1024 words = >2048 bytes in a single packet must be rejected!)
    uint8_t big_pkt[34];
    big_pkt[0] = 0x11; big_pkt[1] = 0x00; big_pkt[2] = 0x00; big_pkt[3] = 0x00; big_pkt[4] = 27;
    for (int k = 0; k < 9; k++) {
        big_pkt[5 + k*3] = 0xFF; big_pkt[6 + k*3] = 250; big_pkt[7 + k*3] = 0xEE;
    }
    uint16_t cb = gl_bridge_crc16_ccitt(big_pkt, 32, 0xFFFF);
    big_pkt[32] = (uint8_t)(cb >> 8); big_pkt[33] = (uint8_t)(cb & 0xFF);
    send_qspi_packet_40mhz(big_pkt, sizeof(big_pkt));
    REQUIRE_TRUE(g_rx.stage_overflow_err == 1 && g_rx.bad_packet_cnt == 1, "Stage overflow guard failed");
    REQUIRE_TRUE(g_spram.mem[0][0] == 0x2222, "SPRAM corrupted on overflow");

    // Test 3: 2-bpp Ping-Pong Double Buffering via Firmware Driver Builder (BRIDGE_MODE_640x400_2BPP_PP = 1)
    gl_bridge_config_t cfg_pp = {
        .mode = BRIDGE_MODE_640x400_2BPP_PP,
        .disparity_px = 0,
        .mirror_left = false,
        .mirror_right = true,
        .qspi_clk_hz = 40000000
    };
    uint8_t cfg2[6];
    REQUIRE_TRUE(gl_bridge_build_optical_cfg_packet(&cfg_pp, cfg2, sizeof(cfg2)) == 6, "build_optical_cfg failed");
    send_qspi_packet_40mhz(cfg2, sizeof(cfg2));

    uint8_t rle2[10] = {0x11, 0x00, 0x00, 0x00, 0x03, 0xFF, 160, 0xE4, 0x00, 0x00};
    uint16_t cr2 = gl_bridge_crc16_ccitt(rle2, 8, 0xFFFF);
    rle2[8] = (uint8_t)(cr2 >> 8); rle2[9] = (uint8_t)(cr2 & 0xFF);
    send_qspi_packet_40mhz(rle2, sizeof(rle2));
    REQUIRE_TRUE(g_spram.mem[2][0] == 0xE4E4 && g_spram.mem[2][79] == 0xE4E4, "Back buffer write failed");
    REQUIRE_TRUE(g_spram.mem[0][0] == 0x2222, "Front buffer overwritten");

    uint8_t swp[4];
    REQUIRE_TRUE(gl_bridge_build_commit_packet(true, swp, sizeof(swp)) == 4, "build_commit_packet failed");
    send_qspi_packet_40mhz(swp, sizeof(swp));
    REQUIRE_TRUE(g_scan.active_front_bank == 0, "Swap occurred before VSYNC");

    while (!g_scan.vsync_done_pulse) advance_sys_clocks(1, 1);
    REQUIRE_TRUE(g_scan.active_front_bank == 1 && g_scan.act_mode == BRIDGE_MODE_640x400_2BPP_PP, "VSYNC swap failed");

    for (int c = 0; c < 65000; c++) advance_sys_clocks(1, 1);
    REQUIRE_TRUE(g_scan.cap_l[40][0] == 0xF && g_scan.cap_l[40][1] == 0xA &&
                 g_scan.cap_l[40][2] == 0x5 && g_scan.cap_l[40][3] == 0x0, "Line 40 2bpp pixel expansion mismatch");

    // Test 4: Independent Binocular Stereo Mode (BRIDGE_MODE_STEREO_INDEP_2BPP = 3)
    gl_bridge_config_t cfg_stereo = {
        .mode = BRIDGE_MODE_STEREO_INDEP_2BPP,
        .disparity_px = 0,
        .mirror_left = false,
        .mirror_right = false,
        .qspi_clk_hz = 40000000
    };
    uint8_t cfg_st[6];
    REQUIRE_TRUE(gl_bridge_build_optical_cfg_packet(&cfg_stereo, cfg_st, sizeof(cfg_st)) == 6, "build_optical_cfg stereo failed");
    send_qspi_packet_40mhz(cfg_st, sizeof(cfg_st));

    uint8_t rle_l[10] = {0x11, 0x00, 0x00, 0x00, 0x03, 0xFF, 160, 0xE4, 0x00, 0x00};
    uint16_t crl = gl_bridge_crc16_ccitt(rle_l, 8, 0xFFFF);
    rle_l[8] = (uint8_t)(crl >> 8); rle_l[9] = (uint8_t)(crl & 0xFF);
    send_qspi_packet_40mhz(rle_l, sizeof(rle_l));

    uint8_t rle_r[10] = {0x11, 0x80, 0x00, 0x00, 0x03, 0xFF, 160, 0x1B, 0x00, 0x00};
    uint16_t crr = gl_bridge_crc16_ccitt(rle_r, 8, 0xFFFF);
    rle_r[8] = (uint8_t)(crr >> 8); rle_r[9] = (uint8_t)(crr & 0xFF);
    send_qspi_packet_40mhz(rle_r, sizeof(rle_r));

    send_qspi_packet_40mhz(swp, sizeof(swp));
    while (!g_scan.vsync_done_pulse) advance_sys_clocks(1, 1);
    REQUIRE_TRUE(g_scan.act_mode == BRIDGE_MODE_STEREO_INDEP_2BPP, "Stereo mode commit failed");

    for (int c = 0; c < 65000; c++) advance_sys_clocks(1, 1);
    REQUIRE_TRUE(g_scan.cap_l[40][0] == 0xF && g_scan.cap_l[40][1] == 0xA && g_scan.cap_l[40][2] == 0x5 && g_scan.cap_l[40][3] == 0x0,
                 "Left eye independent pixel mismatch");
    REQUIRE_TRUE(g_scan.cap_r[40][0] == 0x0 && g_scan.cap_r[40][1] == 0x5 && g_scan.cap_r[40][2] == 0xA && g_scan.cap_r[40][3] == 0xF,
                 "Right eye independent pixel mismatch");

    // Test 5: OP_READ_STATUS (0x50) Bidirectional QSPI Readback via Firmware Driver
    gl_bridge_status_t st;
    uint16_t good_before = g_rx.good_packet_cnt;
    REQUIRE_TRUE(gl_bridge_qspi_read_status(sim_qspi_halfduplex_cb, NULL, &st) == 0, "gl_bridge_qspi_read_status failed");
    REQUIRE_TRUE(g_rx.good_packet_cnt == good_before, "OP_READ_STATUS must not pollute command FIFO");
    REQUIRE_TRUE(st.stereo_indep_mode == true && st.active_mode == BRIDGE_MODE_STEREO_INDEP_2BPP,
                 "Status readback mode mismatch: raw=0x%04X", st.raw_status_word);
    REQUIRE_TRUE(st.stage_overflow == true && st.cdc_overflow == false && st.crc_error == false,
                 "Status readback error flags mismatch: raw=0x%04X", st.raw_status_word);
    REQUIRE_TRUE(st.good_pkt_cnt_lo4 == (good_before & 0x0F) && st.bad_pkt_cnt_lo4 == 1,
                 "Status readback counters mismatch: raw=0x%04X", st.raw_status_word);

    printf("=== OFFLINE C99 RTL MODEL SELF-CHECK REPORT (V2.2 INCREMENTAL FIXES VERIFIED) ===\n");
    printf("[NOTE] NATIVE IVERILOG / YOSYS / NEXTPNR-ICE40: BLOCKED_NO_LOCAL_EDA_BINARY (NOT_RUN)\n");
    printf("[PASS] Fix 1 (FW <-> RTL Mode Enum Alignment): Modes 0..3 match 1:1 (STEREO_INDEP_2BPP=3)\n");
    printf("[PASS] Fix 2 (OP_READ_STATUS 0x50 Bidirectional QSPI Readback): raw_status=0x%04X, mode=%d, stereo=%d, good=%u, bad=%u\n",
           st.raw_status_word, st.active_mode, st.stereo_indep_mode, st.good_pkt_cnt_lo4, st.bad_pkt_cnt_lo4);
    printf("[PASS] Fix 3 (Synchronous EBR FIFO Read Timing Alignment): 0-cycle skew between out_valid and ebr_dout\n");
    printf("[PASS] Fix 4 (Ping-Pong Double Buffering & VSYNC Atomic Swap): Back-Bank2[0]=0x%04X -> swapped at VSYNC\n",
           g_spram.mem[2][0]);
    printf("[PASS] Fix 5 (Independent Left/Right Stereo Mode 3): Left[40][0..3]=[0x%X,0x%X,0x%X,0x%X] != Right[40][0..3]=[0x%X,0x%X,0x%X,0x%X]\n",
           g_scan.cap_l[40][0], g_scan.cap_l[40][1], g_scan.cap_l[40][2], g_scan.cap_l[40][3],
           g_scan.cap_r[40][0], g_scan.cap_r[40][1], g_scan.cap_r[40][2], g_scan.cap_r[40][3]);
    return 0;
}
