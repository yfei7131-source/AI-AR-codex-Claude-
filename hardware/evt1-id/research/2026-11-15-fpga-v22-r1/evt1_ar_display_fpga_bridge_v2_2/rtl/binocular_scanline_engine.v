// SPDX-License-Identifier: MIT
// Module:   binocular_scanline_engine
// Standard: IEEE 1364-2005 Verilog
// Purpose:  1. Dual Independent Left (`line_buf_l`) & Right (`line_buf_r`) Scanline Buffers
//              supporting True Independent Stereo Image Mode (`MODE_STEREO_INDEP_2BPP = 2'b11`)
//              as well as Shared 4-bpp (2'b00), Ping-Pong 2-bpp (2'b01), and Full 480p 2-bpp (2'b10).
//           2. Multiplier-free line address accumulator (`line_base_waddr`), eliminating the
//              10x8 multiplier from the critical SPRAM address path for >85 MHz Fmax.

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module binocular_scanline_engine #(
    parameter VBLANK_CLOCKS = 17'd102080
) (
    input  wire               clk_sys,
    input  wire               rst_n,
    input  wire [1:0]         cfg_mode,
    input  wire signed [7:0]  cfg_disparity_px,
    input  wire               cfg_mirror_left,
    input  wire               cfg_mirror_right,
    input  wire               frame_commit_req,
    input  wire               commit_swap_en,
    input  wire [7:0]         cmd_lut_waddr,
    input  wire [7:0]         cmd_lut_wdata,
    input  wire               cmd_lut_we,
    output reg                spram_re,
    output reg  [15:0]        spram_raddr,
    input  wire [15:0]        spram_rdata_l,
    input  wire [15:0]        spram_rdata_r,
    input  wire               spram_rvalid,
    output reg                opt_sclk,
    output reg                opt_cs_l_n,
    output reg                opt_cs_r_n,
    output reg  [3:0]         opt_l_io,
    output reg  [3:0]         opt_r_io,
    output reg                vsync_done_pulse,
    output reg                active_front_bank,
    output wire               stereo_indep_mode,
    output reg  [1:0]         act_mode,
    output reg                commit_pending
);

    // Dual Independent Line Buffers (640 x 4-bit each; NO async reset loop so Yosys can map cleanly)
    reg [3:0] line_buf_l [0:639];
    reg [3:0] line_buf_r [0:639];

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

    reg [7:0] cmd_lut [0:15];
    integer i;

    reg signed [7:0] act_disparity_px;
    reg              act_mirror_l;
    reg              act_mirror_r;
    reg              swap_pending;

    assign stereo_indep_mode = (act_mode == `MODE_STEREO_INDEP_2BPP);

    localparam S_FETCH_LINE  = 3'd0,
               S_FETCH_DRAIN = 3'd1,
               S_CS_SETUP    = 3'd2,
               S_LINE_HDR    = 3'd3,
               S_TX_PIXELS   = 3'd4,
               S_CS_HOLD     = 3'd5,
               S_NEXT_LINE   = 3'd6,
               S_VBLANK      = 3'd7;

    reg [2:0]  state;
    reg [9:0]  cur_y;
    reg [15:0] line_base_waddr;
    reg [7:0]  fetch_word_idx;
    reg [7:0]  fetch_idx_d1, fetch_idx_d2;
    reg [2:0]  hdr_nib_idx;
    reg [9:0]  tx_x;
    reg [16:0] vblank_cnt;

    wire is_2bpp_mode = (act_mode != `MODE_640x400_4BPP);
    wire [7:0]  last_word_idx  = is_2bpp_mode ? 8'd79  : 8'd159;
    wire [15:0] words_per_line = is_2bpp_mode ? 16'd80 : 16'd160;

    wire active_row = (act_mode == `MODE_640x480_2BPP) ? 1'b1 :
                      ((cur_y >= `ACTIVE_Y_OFFSET) && (cur_y < (`ACTIVE_Y_OFFSET + `ACTIVE_WIN_HEIGHT)));

    wire [15:0] bank_base = ((act_mode == `MODE_640x400_2BPP_PP) && active_front_bank) ? 16'h8000 : 16'h0000;

    wire signed [10:0] base_x_l = act_mirror_l ? (11'sd639 - $signed({1'b0, tx_x})) : $signed({1'b0, tx_x});
    wire signed [10:0] base_x_r = act_mirror_r ? (11'sd639 - $signed({1'b0, tx_x})) : $signed({1'b0, tx_x});
    wire signed [10:0] shift_l  = base_x_l + ($signed(act_disparity_px) >>> 1);
    wire signed [10:0] shift_r  = base_x_r - ($signed(act_disparity_px) >>> 1);

    wire l_valid = active_row && (shift_l >= 11'sd0) && (shift_l < 11'sd640);
    wire r_valid = active_row && (shift_r >= 11'sd0) && (shift_r < 11'sd640);

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

    // Synchronous write to line_buf_l and line_buf_r (NO async reset on RAM array!)
    always @(posedge clk_sys) begin
        if (spram_rvalid) begin
            if (is_2bpp_mode) begin
                line_buf_l[{fetch_idx_d2[6:0], 3'b000}] <= expand_2bpp(spram_rdata_l[15:14]);
                line_buf_l[{fetch_idx_d2[6:0], 3'b001}] <= expand_2bpp(spram_rdata_l[13:12]);
                line_buf_l[{fetch_idx_d2[6:0], 3'b010}] <= expand_2bpp(spram_rdata_l[11:10]);
                line_buf_l[{fetch_idx_d2[6:0], 3'b011}] <= expand_2bpp(spram_rdata_l[9:8]);
                line_buf_l[{fetch_idx_d2[6:0], 3'b100}] <= expand_2bpp(spram_rdata_l[7:6]);
                line_buf_l[{fetch_idx_d2[6:0], 3'b101}] <= expand_2bpp(spram_rdata_l[5:4]);
                line_buf_l[{fetch_idx_d2[6:0], 3'b110}] <= expand_2bpp(spram_rdata_l[3:2]);
                line_buf_l[{fetch_idx_d2[6:0], 3'b111}] <= expand_2bpp(spram_rdata_l[1:0]);

                line_buf_r[{fetch_idx_d2[6:0], 3'b000}] <= expand_2bpp(spram_rdata_r[15:14]);
                line_buf_r[{fetch_idx_d2[6:0], 3'b001}] <= expand_2bpp(spram_rdata_r[13:12]);
                line_buf_r[{fetch_idx_d2[6:0], 3'b010}] <= expand_2bpp(spram_rdata_r[11:10]);
                line_buf_r[{fetch_idx_d2[6:0], 3'b011}] <= expand_2bpp(spram_rdata_r[9:8]);
                line_buf_r[{fetch_idx_d2[6:0], 3'b100}] <= expand_2bpp(spram_rdata_r[7:6]);
                line_buf_r[{fetch_idx_d2[6:0], 3'b101}] <= expand_2bpp(spram_rdata_r[5:4]);
                line_buf_r[{fetch_idx_d2[6:0], 3'b110}] <= expand_2bpp(spram_rdata_r[3:2]);
                line_buf_r[{fetch_idx_d2[6:0], 3'b111}] <= expand_2bpp(spram_rdata_r[1:0]);
            end else begin
                line_buf_l[{fetch_idx_d2, 2'b00}] <= spram_rdata_l[15:12];
                line_buf_l[{fetch_idx_d2, 2'b01}] <= spram_rdata_l[11:8];
                line_buf_l[{fetch_idx_d2, 2'b10}] <= spram_rdata_l[7:4];
                line_buf_l[{fetch_idx_d2, 2'b11}] <= spram_rdata_l[3:0];

                line_buf_r[{fetch_idx_d2, 2'b00}] <= spram_rdata_r[15:12];
                line_buf_r[{fetch_idx_d2, 2'b01}] <= spram_rdata_r[11:8];
                line_buf_r[{fetch_idx_d2, 2'b10}] <= spram_rdata_r[7:4];
                line_buf_r[{fetch_idx_d2, 2'b11}] <= spram_rdata_r[3:0];
            end
        end
    end

    always @(posedge clk_sys or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 16; i = i + 1) cmd_lut[i] <= (i == 0) ? 8'h02 : 8'h00;
            act_mode          <= `MODE_640x400_4BPP;
            act_disparity_px  <= 8'sd8;
            act_mirror_l      <= 1'b0;
            act_mirror_r      <= 1'b1;
            commit_pending    <= 1'b0;
            swap_pending      <= 1'b0;
            active_front_bank <= 1'b0;
            state             <= S_FETCH_LINE;
            cur_y             <= 10'd0;
            line_base_waddr   <= 16'd0;
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
                swap_pending   <= commit_swap_en;
            end

            fetch_idx_d1 <= fetch_word_idx;
            fetch_idx_d2 <= fetch_idx_d1;

            case (state)
                S_FETCH_LINE: begin
                    if (!active_row) begin
                        spram_re <= 1'b0;
                        state    <= S_CS_SETUP;
                    end else begin
                        spram_re    <= 1'b1;
                        spram_raddr <= bank_base + line_base_waddr + {8'd0, fetch_word_idx};
                        if (fetch_word_idx == last_word_idx) begin
                            state <= S_FETCH_DRAIN;
                        end else begin
                            fetch_word_idx <= fetch_word_idx + 8'd1;
                        end
                    end
                end

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
                        opt_l_io <= l_valid ? line_buf_l[shift_l[9:0]] : 4'h0;
                        opt_r_io <= r_valid ? line_buf_r[shift_r[9:0]] : 4'h0;
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
                    if (active_row) begin
                        line_base_waddr <= line_base_waddr + words_per_line;
                    end
                    if (cur_y == 10'd479) begin
                        cur_y            <= 10'd0;
                        line_base_waddr  <= 16'd0;
                        vblank_cnt       <= 17'd0;
                        vsync_done_pulse <= 1'b1;
                        if (commit_pending) begin
                            act_mode         <= cfg_mode;
                            act_disparity_px <= cfg_disparity_px;
                            act_mirror_l     <= cfg_mirror_left;
                            act_mirror_r     <= cfg_mirror_right;
                            if (cfg_mode == `MODE_640x400_2BPP_PP) begin
                                if (swap_pending)
                                    active_front_bank <= ~active_front_bank;
                            end else begin
                                active_front_bank <= 1'b0;
                            end
                            commit_pending <= 1'b0;
                            swap_pending   <= 1'b0;
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
