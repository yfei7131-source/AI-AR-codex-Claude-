// SPDX-License-Identifier: MIT
// Module:   qspi_cdc_async_fifo
// Standard: IEEE 1364-2005 Verilog
// Purpose:  Captures 4-bit QSPI nibbles directly in the 40 MHz s3_sclk domain,
//           assembles 8-bit bytes at 20 MHz, and safely crosses into the 48 MHz
//           clk_sys domain via a 16-deep Dual-Clock Gray-Code Asynchronous FIFO.
//           Eliminates the Nyquist violation of oversampling 40 MHz with 48 MHz.

`timescale 1ns / 1ps

module qspi_cdc_async_fifo (
    // Upstream QSPI Slave Physical Pins (40 MHz s3_sclk domain)
    input  wire       rst_n,
    input  wire       s3_cs_n,
    input  wire       s3_sclk,
    input  wire [3:0] s3_io_in,
    // Downstream System Clock Domain (48 MHz clk_sys domain)
    input  wire       clk_sys,
    input  wire       rd_en,
    output wire [7:0] rd_data,
    output wire       fifo_empty,
    output wire       fifo_full_err,
    output reg        pkt_end_pulse
);

    // -------------------------------------------------------------------------
    // 1. Write Domain: Clocked directly by posedge s3_sclk (Async reset on CS# high)
    // -------------------------------------------------------------------------
    wire csn_async_rst_n = rst_n & (~s3_cs_n);

    reg       nib_phase;
    reg [3:0] hi_nibble;

    // 16-entry x 8-bit dual-port distributed/EBR memory
    reg [7:0] fifo_mem [0:15];
    reg [4:0] wptr_bin;
    reg [4:0] wptr_gray;
    reg       overflow_latched;

    wire [4:0] wptr_bin_next  = wptr_bin + 5'd1;
    wire [4:0] wptr_gray_next = (wptr_bin_next >> 1) ^ wptr_bin_next;

    // Synchronize rptr_gray into s3_sclk domain for full detection
    reg [4:0] rptr_gray;
    reg [4:0] rptr_gray_wsync1, rptr_gray_wsync2;

    wire wfull = (wptr_gray == {~rptr_gray_wsync2[4:3], rptr_gray_wsync2[2:0]});

    always @(posedge s3_sclk or negedge csn_async_rst_n) begin
        if (!csn_async_rst_n) begin
            nib_phase <= 1'b0;
            hi_nibble <= 4'h0;
        end else begin
            if (!nib_phase) begin
                hi_nibble <= s3_io_in;
                nib_phase <= 1'b1;
            end else begin
                nib_phase <= 1'b0;
            end
        end
    end

    // Write pointer advances on every completed byte (2nd nibble edge)
    // Pointer reset is controlled only by system rst_n so remaining bytes drain after s3_cs_n rises!
    always @(posedge s3_sclk or negedge rst_n) begin
        if (!rst_n) begin
            wptr_bin         <= 5'd0;
            wptr_gray        <= 5'd0;
            rptr_gray_wsync1 <= 5'd0;
            rptr_gray_wsync2 <= 5'd0;
            overflow_latched <= 1'b0;
        end else begin
            rptr_gray_wsync1 <= rptr_gray;
            rptr_gray_wsync2 <= rptr_gray_wsync1;
            if (!s3_cs_n && nib_phase) begin
                if (!wfull) begin
                    fifo_mem[wptr_bin[3:0]] <= {hi_nibble, s3_io_in};
                    wptr_bin                <= wptr_bin_next;
                    wptr_gray               <= wptr_gray_next;
                end else begin
                    overflow_latched <= 1'b1;
                end
            end
        end
    end

    // -------------------------------------------------------------------------
    // 2. Read Domain: Clocked by 48 MHz clk_sys
    // -------------------------------------------------------------------------
    reg [4:0] rptr_bin;
    reg [4:0] wptr_gray_rsync1, wptr_gray_rsync2;
    reg [2:0] csn_sys_sync;
    reg       pkt_active;

    wire [4:0] rptr_bin_next  = rptr_bin + 5'd1;
    wire [4:0] rptr_gray_next = (rptr_bin_next >> 1) ^ rptr_bin_next;

    assign fifo_empty    = (rptr_gray == wptr_gray_rsync2);
    assign rd_data       = fifo_mem[rptr_bin[3:0]];
    assign fifo_full_err = overflow_latched;

    always @(posedge clk_sys or negedge rst_n) begin
        if (!rst_n) begin
            rptr_bin         <= 5'd0;
            rptr_gray        <= 5'd0;
            wptr_gray_rsync1 <= 5'd0;
            wptr_gray_rsync2 <= 5'd0;
            csn_sys_sync     <= 3'b111;
            pkt_active       <= 1'b0;
            pkt_end_pulse    <= 1'b0;
        end else begin
            wptr_gray_rsync1 <= wptr_gray;
            wptr_gray_rsync2 <= wptr_gray_rsync1;
            csn_sys_sync     <= {csn_sys_sync[1:0], s3_cs_n};
            pkt_end_pulse    <= 1'b0;

            if (!fifo_empty && rd_en) begin
                rptr_bin  <= rptr_bin_next;
                rptr_gray <= rptr_gray_next;
            end

            // Track packet frame lifecycle: active when CS# low or FIFO not empty
            if (!csn_sys_sync[2] || !fifo_empty) begin
                pkt_active <= 1'b1;
            end else if (pkt_active && csn_sys_sync[2] && fifo_empty) begin
                pkt_active    <= 1'b0;
                pkt_end_pulse <= 1'b1;
            end
        end
    end

endmodule
