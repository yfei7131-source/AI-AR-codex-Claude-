// SPDX-License-Identifier: MIT
// Module:   qspi_cdc_async_fifo
// Standard: IEEE 1364-2005 Verilog
// Purpose:  1. 512-Byte Dual-Clock Gray-Code Asynchronous FIFO backed by 1x SB_RAM40_4K
//              (via ebr_sdp_ram #(.DATA_WIDTH(8), .ADDR_WIDTH(9))).
//           2. Fixed FWFT synchronous EBR read alignment: `rd_data` is driven directly by
//              `ebr_dout` (which registers on `pop_ram`), eliminating the extra `pop_ram_d1`
//              cycle skew so `rd_data` and `~fifo_empty` (`out_valid`) align on the exact
//              same `posedge clk_sys` edge.
//           3. Implements `OP_READ_STATUS (0x50)` bidirectional QSPI status readback over
//              `s3_io_out[3:0]` / `s3_io_oe` without polluting the command FIFO.
//              Uses the 2-clock dummy turnaround window (`cs_nib_cnt == 2..3`) to complete
//              2-FF synchronization (`status_sync1 -> status_sync2`) on gated `s3_sclk`
//              before latching `status_latched` at `cs_nib_cnt == 4'd3`.

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module qspi_cdc_async_fifo (
    input  wire        rst_n,
    input  wire        s3_cs_n,
    input  wire        s3_sclk,
    input  wire [3:0]  s3_io_in,
    output reg  [3:0]  s3_io_out,
    output reg         s3_io_oe,
    input  wire [15:0] status_word_sys,
    input  wire        clk_sys,
    input  wire        rd_en,
    output wire [7:0]  rd_data,
    output wire        fifo_empty,
    output wire        fifo_full_err,
    output reg         pkt_end_pulse
);

    wire csn_async_rst_n = rst_n & (~s3_cs_n);

    reg        nib_phase;
    reg  [3:0] hi_nibble;
    reg  [3:0] cs_nib_cnt;
    reg        is_status_read;
    reg [15:0] status_latched;

    // Synchronize 16-bit status word into gated s3_sclk domain for OP_READ_STATUS (0x50)
    reg [15:0] status_sync1, status_sync2;
    always @(posedge s3_sclk or negedge rst_n) begin
        if (!rst_n) begin
            status_sync1 <= 16'h0000;
            status_sync2 <= 16'h0000;
        end else begin
            status_sync1 <= status_word_sys;
            status_sync2 <= status_sync1;
        end
    end

    reg [9:0] wptr_bin;
    reg [9:0] wptr_gray;
    reg       overflow_latched;

    wire [9:0] wptr_bin_next  = wptr_bin + 10'd1;
    wire [9:0] wptr_gray_next = (wptr_bin_next >> 1) ^ wptr_bin_next;

    reg [9:0] rptr_gray;
    reg [9:0] rptr_gray_wsync1, rptr_gray_wsync2;

    wire [7:0] assembled_byte = {hi_nibble, s3_io_in};
    wire       first_byte_is_read_status = (cs_nib_cnt == 4'd1) && (assembled_byte == `OP_READ_STATUS);
    wire       suppress_fifo_write       = is_status_read || first_byte_is_read_status;

    wire wfull = (wptr_gray == {~rptr_gray_wsync2[9:8], rptr_gray_wsync2[7:0]});
    wire wr_Byte_stb = (!s3_cs_n) && nib_phase && (!wfull) && (!suppress_fifo_write);

    always @(posedge s3_sclk or negedge csn_async_rst_n) begin
        if (!csn_async_rst_n) begin
            nib_phase      <= 1'b0;
            hi_nibble      <= 4'h0;
            cs_nib_cnt     <= 4'd0;
            is_status_read <= 1'b0;
            status_latched <= 16'h0000;
        end else begin
            if (cs_nib_cnt != 4'd15)
                cs_nib_cnt <= cs_nib_cnt + 4'd1;

            if (!nib_phase) begin
                hi_nibble <= s3_io_in;
                nib_phase <= 1'b1;
            end else begin
                nib_phase <= 1'b0;
                if (first_byte_is_read_status) begin
                    is_status_read <= 1'b1;
                end
            end

            // Latch 2-FF synchronized status word at the end of the 2-clock turnaround window
            if (is_status_read && (cs_nib_cnt == 4'd3)) begin
                status_latched <= status_sync2;
            end
        end
    end

    // Launch bidirectional QSPI status readback nibbles on negedge s3_sclk
    // Nibbles 0..1: Opcode 0x50 from host
    // Nibbles 2..3: 1 Dummy/Turnaround byte (bus tri-stated by host; 2-FF status sync completes)
    // Nibbles 4..7: 16-bit status_latched[15:0] driven by FPGA on DISP_D[3:0]
    always @(negedge s3_sclk or negedge csn_async_rst_n) begin
        if (!csn_async_rst_n) begin
            s3_io_oe  <= 1'b0;
            s3_io_out <= 4'h0;
        end else if (is_status_read) begin
            case (cs_nib_cnt)
                4'd4: begin s3_io_oe <= 1'b1; s3_io_out <= status_latched[15:12]; end
                4'd5: begin s3_io_oe <= 1'b1; s3_io_out <= status_latched[11:8];  end
                4'd6: begin s3_io_oe <= 1'b1; s3_io_out <= status_latched[7:4];   end
                4'd7: begin s3_io_oe <= 1'b1; s3_io_out <= status_latched[3:0];   end
                default: begin s3_io_oe <= 1'b0; s3_io_out <= 4'h0; end
            endcase
        end else begin
            s3_io_oe  <= 1'b0;
            s3_io_out <= 4'h0;
        end
    end

    always @(posedge s3_sclk or negedge rst_n) begin
        if (!rst_n) begin
            wptr_bin         <= 10'd0;
            wptr_gray        <= 10'd0;
            rptr_gray_wsync1 <= 10'd0;
            rptr_gray_wsync2 <= 10'd0;
            overflow_latched <= 1'b0;
        end else begin
            rptr_gray_wsync1 <= rptr_gray;
            rptr_gray_wsync2 <= rptr_gray_wsync1;
            if (!s3_cs_n && nib_phase && !suppress_fifo_write) begin
                if (!wfull) begin
                    wptr_bin  <= wptr_bin_next;
                    wptr_gray <= wptr_gray_next;
                end else begin
                    overflow_latched <= 1'b1;
                end
            end
        end
    end

    // Read Domain (48 MHz clk_sys) with FWFT prefetch over synchronous EBR read port
    reg  [9:0] rptr_bin;
    reg  [9:0] wptr_gray_rsync1, wptr_gray_rsync2;
    reg  [2:0] csn_sys_sync;
    reg        pkt_active;
    reg        out_valid;

    wire       raw_ram_empty  = (rptr_gray == wptr_gray_rsync2);
    wire       pop_ram        = (!raw_ram_empty) && (!out_valid || rd_en);
    wire [9:0] rptr_bin_next  = rptr_bin + (pop_ram ? 10'd1 : 10'd0);
    wire [9:0] rptr_gray_next = (rptr_bin_next >> 1) ^ rptr_bin_next;

    ebr_sdp_ram #(
        .DATA_WIDTH(8),
        .ADDR_WIDTH(9)
    ) u_fifo_ebr (
        .wr_clk  (s3_sclk),
        .wr_en   (wr_Byte_stb),
        .wr_addr (wptr_bin[8:0]),
        .wr_data (assembled_byte),
        .rd_clk  (clk_sys),
        .rd_en   (pop_ram),
        .rd_addr (rptr_bin[8:0]),
        .rd_data (rd_data)
    );

    assign fifo_empty    = ~out_valid;
    assign fifo_full_err = overflow_latched;

    always @(posedge clk_sys or negedge rst_n) begin
        if (!rst_n) begin
            rptr_bin         <= 10'd0;
            rptr_gray        <= 10'd0;
            wptr_gray_rsync1 <= 10'd0;
            wptr_gray_rsync2 <= 10'd0;
            csn_sys_sync     <= 3'b111;
            pkt_active       <= 1'b0;
            pkt_end_pulse    <= 1'b0;
            out_valid        <= 1'b0;
        end else begin
            wptr_gray_rsync1 <= wptr_gray;
            wptr_gray_rsync2 <= wptr_gray_rsync1;
            csn_sys_sync     <= {csn_sys_sync[1:0], s3_cs_n};
            pkt_end_pulse    <= 1'b0;

            rptr_bin  <= rptr_bin_next;
            rptr_gray <= rptr_gray_next;

            if (pop_ram)
                out_valid <= 1'b1;
            else if (rd_en)
                out_valid <= 1'b0;

            if (!csn_sys_sync[2] || !raw_ram_empty || out_valid) begin
                pkt_active <= 1'b1;
            end else if (pkt_active && csn_sys_sync[2] && raw_ram_empty && !out_valid) begin
                pkt_active    <= 1'b0;
                pkt_end_pulse <= 1'b1;
            end
        end
    end

endmodule
