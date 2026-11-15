// SPDX-License-Identifier: MIT
// Module:   s3_qspi_slave_rx
// Standard: IEEE 1364-2005 Verilog
// Purpose:  1. Drains 512B CDC FIFO in 48 MHz clk_sys domain with aligned FWFT timing.
//           2. Implements 2-byte/cycle (96 MB/s) RLE4 hardware decompression into
//              a 1024x16-bit (2 KiB) Pre-CRC EBR Staging RAM.
//           3. Guards against stage_ram overflow (>1024 words) and odd-byte misalignment:
//              asserts stage_overflow_err and blocks SPRAM commit on any error.
//           4. Routes writes to Back Buffer (~active_front_bank ? 0x8000 : 0x0000)
//              when in MODE_640x400_2BPP_PP double-buffer mode.
//           5. Exposes bidirectional QSPI readback signals (`s3_io_out`, `s3_io_oe`)
//              for `OP_READ_STATUS (0x50)`.

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module s3_qspi_slave_rx (
    input  wire               clk_sys,
    input  wire               rst_n,
    input  wire               s3_cs_n,
    input  wire               s3_sclk,
    input  wire [3:0]         s3_io_in,
    output wire [3:0]         s3_io_out,
    output wire               s3_io_oe,
    // Handshake & Active State Feedback for Status Readback
    input  wire               spram_host_ready,
    input  wire               active_front_bank,
    input  wire               stereo_indep_mode,
    input  wire [1:0]         act_mode_status,
    input  wire               commit_pending_status,
    output reg                spram_we,
    output reg  [15:0]        spram_waddr,
    output reg  [15:0]        spram_wdata,
    // Decoded Bridge Configuration & Atomic Commit Trigger
    output reg  [1:0]         cfg_mode,
    output reg  signed [7:0]  cfg_disparity_px,
    output reg                cfg_mirror_left,
    output reg                cfg_mirror_right,
    output reg                frame_commit_req,
    output reg                commit_swap_en,
    output reg  [7:0]         cmd_lut_waddr,
    output reg  [7:0]         cmd_lut_wdata,
    output reg                cmd_lut_we,
    // Diagnostics & Error Flags
    output reg                crc_error_flag,
    output wire               cdc_overflow_err,
    output reg                stage_overflow_err,
    output reg  [15:0]        good_packet_cnt,
    output reg  [15:0]        bad_packet_cnt
);

    wire [7:0] fifo_dout;
    wire       fifo_empty;
    wire       pkt_end_pulse;
    wire       fifo_rd_en;

    wire [15:0] status_word_sys = {
        crc_error_flag,
        cdc_overflow_err,
        stage_overflow_err,
        commit_pending_status,
        active_front_bank,
        stereo_indep_mode,
        act_mode_status,
        good_packet_cnt[3:0],
        bad_packet_cnt[3:0]
    };

    qspi_cdc_async_fifo u_cdc_fifo (
        .rst_n           (rst_n),
        .s3_cs_n         (s3_cs_n),
        .s3_sclk         (s3_sclk),
        .s3_io_in        (s3_io_in),
        .s3_io_out       (s3_io_out),
        .s3_io_oe        (s3_io_oe),
        .status_word_sys (status_word_sys),
        .clk_sys         (clk_sys),
        .rd_en           (fifo_rd_en),
        .rd_data         (fifo_dout),
        .fifo_empty      (fifo_empty),
        .fifo_full_err   (cdc_overflow_err),
        .pkt_end_pulse   (pkt_end_pulse)
    );

    // Pre-CRC Staging RAM: 1024 x 16-bit words (2,048 Bytes = 4 EBR blocks)
    reg [15:0] stage_ram [0:1023];
    reg [10:0] stage_wr_count;
    reg [10:0] commit_rd_idx;
    reg [15:0] base_spram_waddr;
    reg        pkt_overflow_latched;

    localparam ST_OPCODE       = 4'd0,
               ST_HDR          = 4'd1,
               ST_PAYLOAD      = 4'd2,
               ST_RLE_EXPAND   = 4'd3,
               ST_CRC_HI       = 4'd4,
               ST_CRC_LO       = 4'd5,
               ST_COMMIT_SPRAM = 4'd6,
               ST_IDLE_WAIT    = 4'd7;

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

    reg [7:0]  rle_run_rem;
    reg [7:0]  rle_val_byte;
    reg [7:0]  upper_byte_hold;
    reg        half_word_valid;

    assign fifo_rd_en = (!fifo_empty) &&
                        (state != ST_RLE_EXPAND) &&
                        (state != ST_COMMIT_SPRAM);

    // Back-buffer base address routing in MODE_640x400_2BPP_PP (2'b01)
    wire [15:0] back_bank_base = (cfg_mode == `MODE_640x400_2BPP_PP) ?
                                 (active_front_bank ? 16'h0000 : 16'h8000) : 16'h0000;
    wire [15:0] masked_offset  = (cfg_mode == `MODE_640x400_2BPP_PP) ?
                                 ((base_spram_waddr + {5'd0, commit_rd_idx}) & 16'h7FFF) :
                                 (base_spram_waddr + {5'd0, commit_rd_idx});

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
            state                <= ST_OPCODE;
            rle_substate         <= RLE_LIT_OR_ESC;
            opcode               <= 8'h00;
            hdr_idx              <= 3'd0;
            hdr_0                <= 8'h00;
            hdr_1                <= 8'h00;
            hdr_2                <= 8'h00;
            hdr_3                <= 8'h00;
            payload_bytes_rem    <= 16'd0;
            crc_reg              <= 16'hFFFF;
            rx_crc_hi            <= 8'h00;
            rle_run_rem          <= 8'd0;
            rle_val_byte         <= 8'h00;
            upper_byte_hold      <= 8'h00;
            half_word_valid      <= 1'b0;
            stage_wr_count       <= 11'd0;
            commit_rd_idx        <= 11'd0;
            base_spram_waddr     <= 16'd0;
            pkt_overflow_latched <= 1'b0;
            spram_we             <= 1'b0;
            spram_waddr          <= 16'd0;
            spram_wdata          <= 16'd0;
            cfg_mode             <= `MODE_640x400_4BPP;
            cfg_disparity_px     <= 8'sd8;
            cfg_mirror_left      <= 1'b0;
            cfg_mirror_right     <= 1'b1;
            frame_commit_req     <= 1'b0;
            commit_swap_en       <= 1'b0;
            cmd_lut_waddr        <= 8'd0;
            cmd_lut_wdata        <= 8'd0;
            cmd_lut_we           <= 1'b0;
            crc_error_flag       <= 1'b0;
            stage_overflow_err   <= 1'b0;
            good_packet_cnt      <= 16'd0;
            bad_packet_cnt       <= 16'd0;
        end else begin
            spram_we         <= 1'b0;
            cmd_lut_we       <= 1'b0;
            frame_commit_req <= 1'b0;

            case (state)
                // -------------------------------------------------------------
                // High-Speed RLE4 Expansion (Supports 2-Byte/Cycle Word Writes)
                // -------------------------------------------------------------
                ST_RLE_EXPAND: begin
                    if (!half_word_valid && (rle_run_rem >= 8'd2)) begin
                        if (stage_wr_count < 11'd1024) begin
                            stage_ram[stage_wr_count[9:0]] <= {rle_val_byte, rle_val_byte};
                            stage_wr_count                 <= stage_wr_count + 11'd1;
                        end else begin
                            pkt_overflow_latched <= 1'b1;
                            stage_overflow_err   <= 1'b1;
                        end
                        if (rle_run_rem == 8'd2) begin
                            rle_run_rem <= 8'd0;
                            state       <= (payload_bytes_rem == 16'd0) ? ST_CRC_HI : ST_PAYLOAD;
                        end else begin
                            rle_run_rem <= rle_run_rem - 8'd2;
                        end
                    end else begin
                        if (!half_word_valid) begin
                            upper_byte_hold <= rle_val_byte;
                            half_word_valid <= 1'b1;
                        end else begin
                            if (stage_wr_count < 11'd1024) begin
                                stage_ram[stage_wr_count[9:0]] <= {upper_byte_hold, rle_val_byte};
                                stage_wr_count                 <= stage_wr_count + 11'd1;
                            end else begin
                                pkt_overflow_latched <= 1'b1;
                                stage_overflow_err   <= 1'b1;
                            end
                            half_word_valid <= 1'b0;
                        end
                        if (rle_run_rem <= 8'd1) begin
                            rle_run_rem <= 8'd0;
                            state       <= (payload_bytes_rem == 16'd0) ? ST_CRC_HI : ST_PAYLOAD;
                        end else begin
                            rle_run_rem <= rle_run_rem - 8'd1;
                        end
                    end
                end

                // -------------------------------------------------------------
                // Post-CRC Verified Commit Burst from Staging EBR -> SPRAM
                // -------------------------------------------------------------
                ST_COMMIT_SPRAM: begin
                    if (commit_rd_idx < stage_wr_count) begin
                        if (spram_host_ready) begin
                            spram_we      <= 1'b1;
                            spram_waddr   <= back_bank_base | masked_offset;
                            spram_wdata   <= stage_ram[commit_rd_idx[9:0]];
                            commit_rd_idx <= commit_rd_idx + 11'd1;
                        end
                    end else begin
                        state <= ST_OPCODE;
                    end
                end

                default: begin
                    if (pkt_end_pulse && state != ST_COMMIT_SPRAM) begin
                        state        <= ST_OPCODE;
                        rle_substate <= RLE_LIT_OR_ESC;
                        crc_reg      <= 16'hFFFF;
                    end else if (fifo_rd_en) begin
                        case (state)
                            ST_OPCODE: begin
                                opcode               <= fifo_dout;
                                crc_reg              <= next_crc16(16'hFFFF, fifo_dout);
                                hdr_idx              <= 3'd0;
                                stage_wr_count       <= 11'd0;
                                half_word_valid      <= 1'b0;
                                pkt_overflow_latched <= 1'b0;
                                rle_substate         <= RLE_LIT_OR_ESC;
                                state                <= ST_HDR;
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
                                    if (!half_word_valid) begin
                                        upper_byte_hold <= fifo_dout;
                                        half_word_valid <= 1'b1;
                                    end else begin
                                        if (stage_wr_count < 11'd1024) begin
                                            stage_ram[stage_wr_count[9:0]] <= {upper_byte_hold, fifo_dout};
                                            stage_wr_count                 <= stage_wr_count + 11'd1;
                                        end else begin
                                            pkt_overflow_latched <= 1'b1;
                                            stage_overflow_err   <= 1'b1;
                                        end
                                        half_word_valid <= 1'b0;
                                    end
                                    if (payload_bytes_rem <= 16'd1)
                                        state <= ST_CRC_HI;
                                end else begin
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
                                                    end else begin
                                                        pkt_overflow_latched <= 1'b1;
                                                        stage_overflow_err   <= 1'b1;
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
                                            if (rle_run_rem == 8'd0) begin
                                                if (payload_bytes_rem <= 16'd1)
                                                    state <= ST_CRC_HI;
                                            end else begin
                                                if (!half_word_valid) begin
                                                    upper_byte_hold <= fifo_dout;
                                                    half_word_valid <= 1'b1;
                                                end else begin
                                                    if (stage_wr_count < 11'd1024) begin
                                                        stage_ram[stage_wr_count[9:0]] <= {upper_byte_hold, fifo_dout};
                                                        stage_wr_count                 <= stage_wr_count + 11'd1;
                                                    end else begin
                                                        pkt_overflow_latched <= 1'b1;
                                                        stage_overflow_err   <= 1'b1;
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
                                if (({rx_crc_hi, fifo_dout} == crc_reg) &&
                                    (!pkt_overflow_latched) &&
                                    (!cdc_overflow_err) &&
                                    (!half_word_valid)) begin
                                    crc_error_flag  <= 1'b0;
                                    good_packet_cnt <= good_packet_cnt + 16'd1;
                                    if (opcode == `OP_SET_OPTICAL_CFG) begin
                                        cfg_mode         <= hdr_0[1:0];
                                        cfg_disparity_px <= $signed(hdr_1);
                                        cfg_mirror_left  <= hdr_2[0];
                                        cfg_mirror_right <= hdr_2[1];
                                        state            <= ST_OPCODE;
                                    end else if (opcode == `OP_LOAD_PANEL_LUT) begin
                                        cmd_lut_waddr <= hdr_0;
                                        cmd_lut_wdata <= hdr_1;
                                        cmd_lut_we    <= 1'b1;
                                        state         <= ST_OPCODE;
                                    end else if (opcode == `OP_COMMIT_FRAME) begin
                                        frame_commit_req <= 1'b1;
                                        commit_swap_en   <= hdr_0[0];
                                        state            <= ST_OPCODE;
                                    end else if (opcode == `OP_WRITE_ROI_RAW || opcode == `OP_WRITE_ROI_RLE4) begin
                                        commit_rd_idx <= 11'd0;
                                        state         <= ST_COMMIT_SPRAM;
                                    end else begin
                                        state <= ST_OPCODE;
                                    end
                                end else begin
                                    crc_error_flag <= ({rx_crc_hi, fifo_dout} != crc_reg);
                                    bad_packet_cnt <= bad_packet_cnt + 16'd1;
                                    stage_wr_count <= 11'd0;
                                    state          <= ST_IDLE_WAIT;
                                end
                            end

                            ST_IDLE_WAIT: begin
                            end
                        endcase
                    end
                end
            endcase
        end
    end

endmodule
