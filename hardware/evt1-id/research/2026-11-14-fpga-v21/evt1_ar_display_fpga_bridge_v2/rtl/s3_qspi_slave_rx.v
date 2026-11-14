// SPDX-License-Identifier: MIT
// Module:   s3_qspi_slave_rx
// Standard: IEEE 1364-2005 Verilog
// Purpose:  Drains bytes from qspi_cdc_async_fifo in the 48 MHz clk_sys domain,
//           verifies CRC-16-CCITT (0x1021), decompresses RLE4 runs in hardware,
//           stages uncommitted pixel words in a 1024x16-bit (2 KiB) EBR Staging RAM,
//           and ONLY commits words to SPRAM AFTER CRC-16 passes (Zero corrupt writes!).

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module s3_qspi_slave_rx (
    input  wire               clk_sys,
    input  wire               rst_n,
    // Physical QSPI Slave Interface from ESP32-S3
    input  wire               s3_cs_n,
    input  wire               s3_sclk,
    input  wire [3:0]         s3_io_in,
    // Handshake with SPRAM Framebuffer Controller
    input  wire               spram_host_ready,
    output reg                spram_we,
    output reg  [15:0]        spram_waddr,
    output reg  [15:0]        spram_wdata,
    // Decoded Bridge Configuration & Atomic Commit Trigger
    output reg  [1:0]         cfg_mode,
    output reg  signed [7:0]  cfg_disparity_px,
    output reg                cfg_mirror_left,
    output reg                cfg_mirror_right,
    output reg                frame_commit_req,
    output reg  [7:0]         cmd_lut_waddr,
    output reg  [7:0]         cmd_lut_wdata,
    output reg                cmd_lut_we,
    // Status & Error Counters
    output reg                crc_error_flag,
    output wire               cdc_overflow_err,
    output reg  [15:0]        good_packet_cnt,
    output reg  [15:0]        bad_packet_cnt
);

    wire [7:0] fifo_dout;
    wire       fifo_empty;
    wire       pkt_end_pulse;
    wire       fifo_rd_en;

    qspi_cdc_async_fifo u_cdc_fifo (
        .rst_n         (rst_n),
        .s3_cs_n       (s3_cs_n),
        .s3_sclk       (s3_sclk),
        .s3_io_in      (s3_io_in),
        .clk_sys       (clk_sys),
        .rd_en         (fifo_rd_en),
        .rd_data       (fifo_dout),
        .fifo_empty    (fifo_empty),
        .fifo_full_err (cdc_overflow_err),
        .pkt_end_pulse (pkt_end_pulse)
    );

    // Pre-CRC EBR Staging Buffer: 1024 x 16-bit words (2,048 Bytes = 4x SB_RAM40_4K EBR)
    // Guarantee: Incoming packets write ONLY to stage_ram. SPRAM is untouched until CRC passes!
    reg [15:0] stage_ram [0:1023];
    reg [10:0] stage_wr_count;
    reg [10:0] commit_rd_idx;
    reg [15:0] base_spram_waddr;

    // FSM States
    localparam ST_OPCODE       = 4'd0,
               ST_HDR          = 4'd1,
               ST_PAYLOAD      = 4'd2,
               ST_RLE_EXPAND   = 4'd3,
               ST_CRC_HI       = 4'd4,
               ST_CRC_LO       = 4'd5,
               ST_COMMIT_SPRAM = 4'd6,
               ST_IDLE_WAIT    = 4'd7;

    // RLE4 Sub-states (Escape token = 8'hFF, followed by [run_len, pixel_byte])
    localparam RLE_LIT_OR_ESC = 2'd0,
               RLE_GET_LEN    = 2'd1,
               RLE_GET_VAL    = 2'd2;

    reg [3:0]  state;
    reg [1:0]  rle_substate;
    reg [7:0]  opcode;
    reg [2:0]  hdr_idx;
    reg [7:0]  hdr_0, hdr_1, hdr_2, hdr_3;
    reg [15:0] payload_bytes_rem;
    reg [15:0] crc_reg;
    reg [7:0]  rx_crc_hi;

    // RLE4 & 16-bit Word Packing Registers
    reg [7:0]  rle_run_rem;
    reg [7:0]  rle_val_byte;
    reg [7:0]  upper_byte_hold;
    reg        half_word_valid;

    // Pause reading from CDC FIFO when expanding multi-byte RLE runs or committing to SPRAM
    assign fifo_rd_en = (!fifo_empty) &&
                        (state != ST_RLE_EXPAND) &&
                        (state != ST_COMMIT_SPRAM);

    // IEEE 1364-2005 compliant CRC-16-CCITT function (poly = 0x1021)
    function [15:0] next_crc16;
        input [15:0] crc_in;
        input [7:0]  data_in;
        integer i;
        reg [15:0] c;
        begin
            c = crc_in ^ {data_in, 8'h00};
            for (i = 0; i < 8; i = i + 1) begin
                if (c[15])
                    c = (c << 1) ^ 16'h1021;
                else
                    c = (c << 1);
            end
            next_crc16 = c;
        end
    endfunction

    always @(posedge clk_sys or negedge rst_n) begin
        if (!rst_n) begin
            state            <= ST_OPCODE;
            rle_substate     <= RLE_LIT_OR_ESC;
            opcode           <= 8'h00;
            hdr_idx          <= 3'd0;
            hdr_0            <= 8'h00;
            hdr_1            <= 8'h00;
            hdr_2            <= 8'h00;
            hdr_3            <= 8'h00;
            payload_bytes_rem<= 16'd0;
            crc_reg          <= 16'hFFFF;
            rx_crc_hi        <= 8'h00;
            rle_run_rem      <= 8'd0;
            rle_val_byte     <= 8'h00;
            upper_byte_hold  <= 8'h00;
            half_word_valid  <= 1'b0;
            stage_wr_count   <= 11'd0;
            commit_rd_idx    <= 11'd0;
            base_spram_waddr <= 16'd0;
            spram_we         <= 1'b0;
            spram_waddr      <= 16'd0;
            spram_wdata      <= 16'd0;
            cfg_mode         <= `MODE_640x400_4BPP;
            cfg_disparity_px <= 8'sd8;
            cfg_mirror_left  <= 1'b0;
            cfg_mirror_right <= 1'b1;
            frame_commit_req <= 1'b0;
            cmd_lut_waddr    <= 8'd0;
            cmd_lut_wdata    <= 8'd0;
            cmd_lut_we       <= 1'b0;
            crc_error_flag   <= 1'b0;
            good_packet_cnt  <= 16'd0;
            bad_packet_cnt   <= 16'd0;
        end else begin
            spram_we         <= 1'b0;
            cmd_lut_we       <= 1'b0;
            frame_commit_req <= 1'b0;

            case (state)
                // -------------------------------------------------------------
                // Hardware RLE4 Multi-Byte Run Expansion into Staging EBR
                // -------------------------------------------------------------
                ST_RLE_EXPAND: begin
                    if (!half_word_valid) begin
                        upper_byte_hold <= rle_val_byte;
                        half_word_valid <= 1'b1;
                    end else begin
                        if (stage_wr_count < 11'd1024) begin
                            stage_ram[stage_wr_count[9:0]] <= {upper_byte_hold, rle_val_byte};
                            stage_wr_count                 <= stage_wr_count + 11'd1;
                        end
                        half_word_valid <= 1'b0;
                    end

                    if (rle_run_rem <= 8'd1) begin
                        rle_run_rem <= 8'd0;
                        if (payload_bytes_rem == 16'd0)
                            state <= ST_CRC_HI;
                        else
                            state <= ST_PAYLOAD;
                    end else begin
                        rle_run_rem <= rle_run_rem - 8'd1;
                    end
                end

                // -------------------------------------------------------------
                // Post-CRC Verified Commit Burst from Staging EBR -> SPRAM
                // -------------------------------------------------------------
                ST_COMMIT_SPRAM: begin
                    if (commit_rd_idx < stage_wr_count) begin
                        if (spram_host_ready) begin
                            spram_we      <= 1'b1;
                            spram_waddr   <= base_spram_waddr + {5'd0, commit_rd_idx};
                            spram_wdata   <= stage_ram[commit_rd_idx[9:0]];
                            commit_rd_idx <= commit_rd_idx + 11'd1;
                        end
                    end else begin
                        state <= ST_OPCODE;
                    end
                end

                // -------------------------------------------------------------
                // Byte-Driven States from Dual-Clock Async CDC FIFO
                // -------------------------------------------------------------
                default: begin
                    if (pkt_end_pulse && state != ST_COMMIT_SPRAM) begin
                        state        <= ST_OPCODE;
                        rle_substate <= RLE_LIT_OR_ESC;
                        crc_reg      <= 16'hFFFF;
                    end else if (fifo_rd_en) begin
                        case (state)
                            ST_OPCODE: begin
                                opcode          <= fifo_dout;
                                crc_reg         <= next_crc16(16'hFFFF, fifo_dout);
                                hdr_idx         <= 3'd0;
                                stage_wr_count  <= 11'd0;
                                half_word_valid <= 1'b0;
                                rle_substate    <= RLE_LIT_OR_ESC;
                                state           <= ST_HDR;
                            end

                            ST_HDR: begin
                                crc_reg <= next_crc16(crc_reg, fifo_dout);
                                case (hdr_idx)
                                    3'd0: hdr_0 <= fifo_dout;
                                    3'd1: hdr_1 <= fifo_dout;
                                    3'd2: hdr_2 <= fifo_dout;
                                    3'd3: hdr_3 <= fifo_dout;
                                    default: ;
                                endcase

                                if (opcode == `OP_COMMIT_FRAME && hdr_idx == 3'd0) begin
                                    state <= ST_CRC_HI;
                                end else if ((opcode == `OP_SET_OPTICAL_CFG || opcode == `OP_LOAD_PANEL_LUT) && hdr_idx == 3'd2) begin
                                    state <= ST_CRC_HI;
                                end else if ((opcode == `OP_WRITE_ROI_RAW || opcode == `OP_WRITE_ROI_RLE4) && hdr_idx == 3'd3) begin
                                    base_spram_waddr  <= {hdr_0, hdr_1};
                                    payload_bytes_rem <= {hdr_2, fifo_dout};
                                    if ({hdr_2, fifo_dout} == 16'd0)
                                        state <= ST_CRC_HI;
                                    else
                                        state <= ST_PAYLOAD;
                                end else begin
                                    hdr_idx <= hdr_idx + 3'd1;
                                end
                            end

                            ST_PAYLOAD: begin
                                crc_reg           <= next_crc16(crc_reg, fifo_dout);
                                payload_bytes_rem <= payload_bytes_rem - 16'd1;

                                if (opcode == `OP_WRITE_ROI_RAW) begin
                                    // Raw 4-bpp pixel pair packing into Pre-CRC Staging RAM
                                    if (!half_word_valid) begin
                                        upper_byte_hold <= fifo_dout;
                                        half_word_valid <= 1'b1;
                                    end else begin
                                        if (stage_wr_count < 11'd1024) begin
                                            stage_ram[stage_wr_count[9:0]] <= {upper_byte_hold, fifo_dout};
                                            stage_wr_count                 <= stage_wr_count + 11'd1;
                                        end
                                        half_word_valid <= 1'b0;
                                    end
                                    if (payload_bytes_rem <= 16'd1)
                                        state <= ST_CRC_HI;
                                end else begin
                                    // Hardware RLE4 Stream Decoder ([0xFF, count, val] or literal != 0xFF)
                                    case (rle_substate)
                                        RLE_LIT_OR_ESC: begin
                                            if (fifo_dout == 8'hFF) begin
                                                rle_substate <= RLE_GET_LEN;
                                            end else begin
                                                if (!half_word_valid) begin
                                                    upper_byte_hold <= fifo_dout;
                                                    half_word_valid <= 1'b1;
                                                end else begin
                                                    if (stage_wr_count < 11'd1024) begin
                                                        stage_ram[stage_wr_count[9:0]] <= {upper_byte_hold, fifo_dout};
                                                        stage_wr_count                 <= stage_wr_count + 11'd1;
                                                    end
                                                    half_word_valid <= 1'b0;
                                                end
                                                if (payload_bytes_rem <= 16'd1)
                                                    state <= ST_CRC_HI;
                                            end
                                        end

                                        RLE_GET_LEN: begin
                                            rle_run_rem  <= fifo_dout;
                                            rle_substate <= RLE_GET_VAL;
                                        end

                                        RLE_GET_VAL: begin
                                            rle_val_byte <= fifo_dout;
                                            rle_substate <= RLE_LIT_OR_ESC;
                                            // Expand 1st byte immediately, remaining (rle_run_rem - 1) in ST_RLE_EXPAND
                                            if (!half_word_valid) begin
                                                upper_byte_hold <= fifo_dout;
                                                half_word_valid <= 1'b1;
                                            end else begin
                                                if (stage_wr_count < 11'd1024) begin
                                                    stage_ram[stage_wr_count[9:0]] <= {upper_byte_hold, fifo_dout};
                                                    stage_wr_count                 <= stage_wr_count + 11'd1;
                                                end
                                                half_word_valid <= 1'b0;
                                            end

                                            if (rle_run_rem > 8'd1) begin
                                                rle_run_rem <= rle_run_rem - 8'd1;
                                                state       <= ST_RLE_EXPAND;
                                            end else if (payload_bytes_rem <= 16'd1) begin
                                                state <= ST_CRC_HI;
                                            end
                                        end

                                        default: rle_substate <= RLE_LIT_OR_ESC;
                                    endcase
                                end
                            end

                            ST_CRC_HI: begin
                                rx_crc_hi <= fifo_dout;
                                state     <= ST_CRC_LO;
                            end

                            ST_CRC_LO: begin
                                // Strict Post-CRC Commit Gate
                                if ({rx_crc_hi, fifo_dout} == crc_reg) begin
                                    crc_error_flag  <= 1'b0;
                                    good_packet_cnt <= good_packet_cnt + 16'd1;
                                    if (opcode == `OP_SET_OPTICAL_CFG) begin
                                        cfg_mode         <= hdr_0[1:0];
                                        cfg_disparity_px <= $signed(hdr_1);
                                        cfg_mirror_left  <= hdr_2[0];
                                        cfg_mirror_right <= hdr_2[1];
                                        state            <= ST_IDLE_WAIT;
                                    end else if (opcode == `OP_LOAD_PANEL_LUT) begin
                                        cmd_lut_waddr <= hdr_0;
                                        cmd_lut_wdata <= hdr_1;
                                        cmd_lut_we    <= 1'b1;
                                        state         <= ST_IDLE_WAIT;
                                    end else if (opcode == `OP_COMMIT_FRAME) begin
                                        frame_commit_req <= 1'b1;
                                        state            <= ST_IDLE_WAIT;
                                    end else if (opcode == `OP_WRITE_ROI_RAW || opcode == `OP_WRITE_ROI_RLE4) begin
                                        commit_rd_idx <= 11'd0;
                                        state         <= ST_COMMIT_SPRAM;
                                    end else begin
                                        state <= ST_IDLE_WAIT;
                                    end
                                end else begin
                                    // CRC MISMATCH: Discard staged data, SPRAM is 100% protected!
                                    crc_error_flag <= 1'b1;
                                    bad_packet_cnt <= bad_packet_cnt + 16'd1;
                                    stage_wr_count <= 11'd0;
                                    state          <= ST_IDLE_WAIT;
                                end
                            end

                            ST_IDLE_WAIT: begin
                                // Wait for CS# deassertion pulse to reset for next packet
                            end
                        endcase
                    end
                end
            endcase
        end
    end

endmodule
