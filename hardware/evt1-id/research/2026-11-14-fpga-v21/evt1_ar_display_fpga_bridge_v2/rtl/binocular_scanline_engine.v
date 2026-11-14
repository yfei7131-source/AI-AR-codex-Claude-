// SPDX-License-Identifier: MIT
// Module:   binocular_scanline_engine
// Standard: IEEE 1364-2005 Verilog
// Purpose:  1. Latches shadow configuration & Ping-Pong bank selection ONLY at VSYNC
//              boundaries after frame_commit_req (Atomic tear-free frame commit).
//           2. Fetches 160 words (640 pixels) per active scanline with pipelined
//              fetch_idx_d1 (fixes the 160th word underflow bug at x=636..639).
//           3. Generates realistic QSPI Panel Timing: CS# setup, programmable row header
//              from CMD_LUT, 640-pixel synchronous Dual-Eye QSPI burst (Left normal +d/2,
//              Right horizontally mirrored 639-x -d/2, 0-cycle inter-ocular skew),
//              CS# hold, and 60.00 Hz Vertical Blanking (102,080 clocks VBlank @ 48 MHz).

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module binocular_scanline_engine #(
    parameter VBLANK_CLOCKS = 17'd102080 // 60.00 Hz exact frame lock @ 48 MHz (sim can override to 16)
) (
    input  wire               clk_sys,
    input  wire               rst_n,
    // Shadowable Host Config + Atomic Commit Handshake
    input  wire [1:0]         cfg_mode,
    input  wire signed [7:0]  cfg_disparity_px,
    input  wire               cfg_mirror_left,
    input  wire               cfg_mirror_right,
    input  wire               frame_commit_req,
    // Runtime-Loadable Panel Command LUT Port (Decouples JBD NDA Opcodes)
    input  wire [7:0]         cmd_lut_waddr,
    input  wire [7:0]         cmd_lut_wdata,
    input  wire               cmd_lut_we,
    // SPRAM Scanline Fetch Port
    output reg                spram_re,
    output reg  [15:0]        spram_raddr,
    input  wire [15:0]        spram_rdata,
    input  wire               spram_rvalid,
    // Dual JBD 0.13" QSPI Master Physical Interface
    output reg                opt_sclk,
    output reg                opt_cs_l_n,
    output reg                opt_cs_r_n,
    output reg  [3:0]         opt_l_io,
    output reg  [3:0]         opt_r_io,
    output reg                vsync_done_pulse,
    output reg                active_front_bank
);

    // EBR Line Buffer: 640 pixels x 4-bit
    reg [3:0] line_buf [0:639];

    // 4-Level (2-bit -> 4-bit) Gamma LUT for Full-Panel 640x480 2-bpp Mode
    function [3:0] expand_2bpp;
        input [1:0] p2;
        begin
            case (p2)
                2'b00: expand_2bpp = 4'h0;
                2'b01: expand_2bpp = 4'h5;
                2'b10: expand_2bpp = 4'hA;
                2'b11: expand_2bpp = 4'hF;
            endcase
        end
    endfunction

    // Runtime-programmable Panel Command LUT (16 bytes; default entry 0 = 8'h02 Page/Row Write)
    reg [7:0] cmd_lut [0:15];
    integer i;

    // Active (VSYNC-locked) Shadow Registers for Atomic Frame Commit
    reg [1:0]        act_mode;
    reg signed [7:0] act_disparity_px;
    reg              act_mirror_l;
    reg              act_mirror_r;
    reg              commit_pending;

    // Scanline Timing State Machine
    localparam S_FETCH_LINE  = 3'd0,
               S_FETCH_DRAIN = 3'd1,
               S_CS_SETUP    = 3'd2,
               S_LINE_HDR    = 3'd3,
               S_TX_PIXELS   = 3'd4,
               S_CS_HOLD     = 3'd5,
               S_NEXT_LINE   = 3'd6,
               S_VBLANK      = 3'd7;

    reg [2:0]  state;
    reg [9:0]  cur_y;           // 0..479
    reg [7:0]  fetch_word_idx;  // 0..159
    reg [7:0]  fetch_idx_d1, fetch_idx_d2; // 2-stage pipeline matching spram_re + SB_SPRAM256KA
    reg [2:0]  hdr_nib_idx;     // 0..5 (6 nibbles = 3-byte row header: [CMD, Y_HI, Y_LO])
    reg [9:0]  tx_x;            // 0..639
    reg [16:0] vblank_cnt;

    wire active_row = (act_mode == `MODE_640x480_2BPP) ? 1'b1 :
                      ((cur_y >= `ACTIVE_Y_OFFSET) && (cur_y < (`ACTIVE_Y_OFFSET + `ACTIVE_WIN_HEIGHT)));
    wire [9:0] spram_y = (act_mode == `MODE_640x480_2BPP) ? cur_y : (cur_y - `ACTIVE_Y_OFFSET);

    // Bank offset for Ping-Pong double buffering in MODE_640x400_2BPP_PP
    wire [15:0] bank_base = (act_mode == `MODE_640x400_2BPP_PP && active_front_bank) ? 16'h8000 : 16'h0000;

    // Binocular Left & Right X coordinate computation (combinational, 0-cycle skew)
    wire signed [10:0] base_x_l = act_mirror_l ? (11'sd639 - $signed({1'b0, tx_x})) : $signed({1'b0, tx_x});
    wire signed [10:0] base_x_r = act_mirror_r ? (11'sd639 - $signed({1'b0, tx_x})) : $signed({1'b0, tx_x});
    wire signed [10:0] shift_l  = base_x_l + ($signed(act_disparity_px) >>> 1);
    wire signed [10:0] shift_r  = base_x_r - ($signed(act_disparity_px) >>> 1);

    wire l_valid = active_row && (shift_l >= 11'sd0) && (shift_l < 11'sd640);
    wire r_valid = active_row && (shift_r >= 11'sd0) && (shift_r < 11'sd640);

    // Header nibble selector: sends [cmd_lut[0], 6'b0, cur_y[9:8], cur_y[7:0]]
    wire [23:0] line_hdr_word = {cmd_lut[0], 6'd0, cur_y[9:8], cur_y[7:0]};
    reg  [3:0]  hdr_nibble;
    always @(*) begin
        case (hdr_nib_idx)
            3'd0: hdr_nibble = line_hdr_word[23:20];
            3'd1: hdr_nibble = line_hdr_word[19:16];
            3'd2: hdr_nibble = line_hdr_word[15:12];
            3'd3: hdr_nibble = line_hdr_word[11:8];
            3'd4: hdr_nibble = line_hdr_word[7:4];
            default: hdr_nibble = line_hdr_word[3:0];
        endcase
    end

    always @(posedge clk_sys or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 16; i = i + 1) cmd_lut[i] <= (i == 0) ? 8'h02 : 8'h00;
            act_mode          <= `MODE_640x400_4BPP;
            act_disparity_px  <= 8'sd8;
            act_mirror_l      <= 1'b0;
            act_mirror_r      <= 1'b1;
            commit_pending    <= 1'b0;
            active_front_bank <= 1'b0;
            state             <= S_FETCH_LINE;
            cur_y             <= 10'd0;
            fetch_word_idx    <= 8'd0;
            fetch_idx_d1      <= 8'd0;
            fetch_idx_d2      <= 8'd0;
            hdr_nib_idx       <= 3'd0;
            tx_x              <= 10'd0;
            vblank_cnt        <= 17'd0;
            spram_re          <= 1'b0;
            spram_raddr       <= 16'd0;
            opt_sclk          <= 1'b0;
            opt_cs_l_n        <= 1'b1;
            opt_cs_r_n        <= 1'b1;
            opt_l_io          <= 4'h0;
            opt_r_io          <= 4'h0;
            vsync_done_pulse  <= 1'b0;
        end else begin
            vsync_done_pulse <= 1'b0;

            if (cmd_lut_we) begin
                cmd_lut[cmd_lut_waddr[3:0]] <= cmd_lut_wdata;
            end

            if (frame_commit_req) begin
                commit_pending <= 1'b1;
            end

            // Pipeline fetch_idx_d1 to match 1-cycle SPRAM read latency
            fetch_idx_d1 <= fetch_word_idx;
            fetch_idx_d2 <= fetch_idx_d1;

            if (spram_rvalid) begin
                line_buf[{fetch_idx_d2, 2'b00}] <= spram_rdata[15:12];
                line_buf[{fetch_idx_d2, 2'b01}] <= spram_rdata[11:8];
                line_buf[{fetch_idx_d2, 2'b10}] <= spram_rdata[7:4];
                line_buf[{fetch_idx_d2, 2'b11}] <= spram_rdata[3:0];
            end

            case (state)
                S_FETCH_LINE: begin
                    if (!active_row) begin
                        spram_re <= 1'b0;
                        state    <= S_CS_SETUP;
                    end else begin
                        spram_re    <= 1'b1;
                        spram_raddr <= bank_base + (spram_y * 16'd160) + {8'd0, fetch_word_idx};
                        if (fetch_word_idx == 8'd159) begin
                            state <= S_FETCH_DRAIN;
                        end else begin
                            fetch_word_idx <= fetch_word_idx + 8'd1;
                        end
                    end
                end

                // Extra drain cycle ensures the 160th word (fetch_idx_d1=159, x=636..639) is latched!
                S_FETCH_DRAIN: begin
                    spram_re       <= 1'b0;
                    fetch_word_idx <= 8'd0;
                    if (!spram_re && !spram_rvalid)
                        state <= S_CS_SETUP;
                end

                S_CS_SETUP: begin
                    opt_cs_l_n  <= 1'b0;
                    opt_cs_r_n  <= 1'b0;
                    opt_sclk    <= 1'b0;
                    hdr_nib_idx <= 3'd0;
                    state       <= S_LINE_HDR;
                end

                S_LINE_HDR: begin
                    if (!opt_sclk) begin
                        opt_l_io <= hdr_nibble;
                        opt_r_io <= hdr_nibble;
                        opt_sclk <= 1'b1;
                    end else begin
                        opt_sclk <= 1'b0;
                        if (hdr_nib_idx == 3'd5) begin
                            tx_x  <= 10'd0;
                            state <= S_TX_PIXELS;
                        end else begin
                            hdr_nib_idx <= hdr_nib_idx + 3'd1;
                        end
                    end
                end

                S_TX_PIXELS: begin
                    if (!opt_sclk) begin
                        opt_l_io <= l_valid ? line_buf[shift_l[9:0]] : 4'h0;
                        opt_r_io <= r_valid ? line_buf[shift_r[9:0]] : 4'h0;
                        opt_sclk <= 1'b1;
                    end else begin
                        opt_sclk <= 1'b0;
                        if (tx_x == 10'd639) begin
                            state <= S_CS_HOLD;
                        end else begin
                            tx_x <= tx_x + 10'd1;
                        end
                    end
                end

                S_CS_HOLD: begin
                    opt_cs_l_n <= 1'b1;
                    opt_cs_r_n <= 1'b1;
                    state      <= S_NEXT_LINE;
                end

                S_NEXT_LINE: begin
                    if (cur_y == 10'd479) begin
                        cur_y            <= 10'd0;
                        vblank_cnt       <= 17'd0;
                        vsync_done_pulse <= 1'b1;
                        // Atomic Commit Update at exact VSYNC boundary
                        if (commit_pending) begin
                            act_mode          <= cfg_mode;
                            act_disparity_px  <= cfg_disparity_px;
                            act_mirror_l      <= cfg_mirror_left;
                            act_mirror_r      <= cfg_mirror_right;
                            active_front_bank <= ~active_front_bank;
                            commit_pending    <= 1'b0;
                        end
                        state <= S_VBLANK;
                    end else begin
                        cur_y <= cur_y + 10'd1;
                        state <= S_FETCH_LINE;
                    end
                end

                S_VBLANK: begin
                    if (vblank_cnt >= VBLANK_CLOCKS) begin
                        vblank_cnt <= 17'd0;
                        state      <= S_FETCH_LINE;
                    end else begin
                        vblank_cnt <= vblank_cnt + 17'd1;
                    end
                end

                default: state <= S_FETCH_LINE;
            endcase
        end
    end

endmodule
