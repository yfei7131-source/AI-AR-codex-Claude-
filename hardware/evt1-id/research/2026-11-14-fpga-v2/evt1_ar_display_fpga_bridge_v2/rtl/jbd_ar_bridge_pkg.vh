// SPDX-License-Identifier: MIT
// Project: Zhiyuan AI/AR Smart Glasses V1.0 (EVT-1 Binocular AR Display Bridge)
// File:    rtl/jbd_ar_bridge_pkg.vh
// Standard: IEEE 1364-2005 Verilog

`ifndef JBD_AR_BRIDGE_PKG_VH
`define JBD_AR_BRIDGE_PKG_VH

`define PANEL_WIDTH          10'd640
`define PANEL_HEIGHT         10'd480
`define ACTIVE_WIN_HEIGHT    10'd400
`define ACTIVE_Y_OFFSET      10'd40

// Operating Modes
`define MODE_640x400_4BPP    2'b00  // 128,000 B in 4x SB_SPRAM256KA (97.66% util), 4-bit native
`define MODE_640x400_2BPP_PP 2'b01  // 64,000 B x 2 Ping-Pong double buffer in 4x SPRAM
`define MODE_640x480_2BPP    2'b10  // 76,800 B full-panel 2-bit -> 4-bit Gamma LUT expansion

// Host-to-Bridge QSPI Protocol Opcodes
`define OP_NOP               8'h00
`define OP_WRITE_ROI_RAW     8'h10  // [0x10, waddr_hi, waddr_lo, len_hi, len_lo, raw_bytes..., crc_hi, crc_lo]
`define OP_WRITE_ROI_RLE4    8'h11  // [0x11, waddr_hi, waddr_lo, len_hi, len_lo, rle_bytes..., crc_hi, crc_lo]
`define OP_SET_OPTICAL_CFG   8'h20  // [0x20, mode, disparity_px_s8, mirror_mask, crc_hi, crc_lo]
`define OP_LOAD_PANEL_LUT    8'h30  // [0x30, lut_addr, lut_byte, dummy, crc_hi, crc_lo] (NDA Command LUT)
`define OP_COMMIT_FRAME      8'h40  // [0x40, commit_flags, crc_hi, crc_lo] (Atomic commit on VSYNC)

`endif
