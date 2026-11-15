// SPDX-License-Identifier: MIT
// Module:   spram_framebuffer_ctrl
// Standard: IEEE 1364-2005 Verilog
// Purpose:  4x SB_SPRAM256KA (128 KiB) controller supporting:
//           1. Parallel Dual-Eye Scanline Read in MODE_STEREO_INDEP_2BPP (2'b11):
//              Simultaneously reads Left Eye word (`scan_rdata_l`) from Banks 0..1
//              and Right Eye word (`scan_rdata_r`) from Banks 2..3 in the same cycle!
//           2. Concurrent zero-wait-state writes to Back Banks while scanning Front Banks
//              in MODE_640x400_2BPP_PP (2'b01).

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module spram_framebuffer_ctrl (
    input  wire        clk_sys,
    input  wire        rst_n,
    input  wire        stereo_indep_mode,
    output wire        host_ready,
    input  wire        host_we,
    input  wire [15:0] host_waddr,
    input  wire [15:0] host_wdata,
    input  wire        scan_re,
    input  wire [15:0] scan_raddr,
    output wire [15:0] scan_rdata_l,
    output wire [15:0] scan_rdata_r,
    output reg         scan_rvalid
);

    wire [1:0] w_bank = host_waddr[15:14];
    wire [1:0] r_bank = scan_raddr[15:14];

    // In stereo_indep_mode, scan_re reads BOTH bank (0, r_bank[0]) for Left and bank (1, r_bank[0]) for Right
    wire scan_uses_b0 = scan_re && (stereo_indep_mode ? (r_bank[0] == 1'b0) : (r_bank == 2'd0));
    wire scan_uses_b1 = scan_re && (stereo_indep_mode ? (r_bank[0] == 1'b1) : (r_bank == 2'd1));
    wire scan_uses_b2 = scan_re && (stereo_indep_mode ? (r_bank[0] == 1'b0) : (r_bank == 2'd2));
    wire scan_uses_b3 = scan_re && (stereo_indep_mode ? (r_bank[0] == 1'b1) : (r_bank == 2'd3));

    wire bank_conflict = (w_bank == 2'd0 && scan_uses_b0) ||
                         (w_bank == 2'd1 && scan_uses_b1) ||
                         (w_bank == 2'd2 && scan_uses_b2) ||
                         (w_bank == 2'd3 && scan_uses_b3);
    assign host_ready  = ~bank_conflict;

    wire [13:0] addr_b0 = scan_uses_b0 ? scan_raddr[13:0] : host_waddr[13:0];
    wire [13:0] addr_b1 = scan_uses_b1 ? scan_raddr[13:0] : host_waddr[13:0];
    wire [13:0] addr_b2 = scan_uses_b2 ? scan_raddr[13:0] : host_waddr[13:0];
    wire [13:0] addr_b3 = scan_uses_b3 ? scan_raddr[13:0] : host_waddr[13:0];

    wire we_b0 = host_we && (w_bank == 2'd0) && (!scan_uses_b0);
    wire we_b1 = host_we && (w_bank == 2'd1) && (!scan_uses_b1);
    wire we_b2 = host_we && (w_bank == 2'd2) && (!scan_uses_b2);
    wire we_b3 = host_we && (w_bank == 2'd3) && (!scan_uses_b3);

    wire cs_b0 = scan_uses_b0 || (host_we && (w_bank == 2'd0));
    wire cs_b1 = scan_uses_b1 || (host_we && (w_bank == 2'd1));
    wire cs_b2 = scan_uses_b2 || (host_we && (w_bank == 2'd2));
    wire cs_b3 = scan_uses_b3 || (host_we && (w_bank == 2'd3));

    wire [15:0] bank_dout_0, bank_dout_1, bank_dout_2, bank_dout_3;
    reg  [1:0]  r_bank_d1;
    reg         stereo_d1;

    SB_SPRAM256KA u_spram0 (
        .ADDRESS(addr_b0), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN(we_b0), .CHIPSELECT(cs_b0), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_0)
    );
    SB_SPRAM256KA u_spram1 (
        .ADDRESS(addr_b1), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN(we_b1), .CHIPSELECT(cs_b1), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_1)
    );
    SB_SPRAM256KA u_spram2 (
        .ADDRESS(addr_b2), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN(we_b2), .CHIPSELECT(cs_b2), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_2)
    );
    SB_SPRAM256KA u_spram3 (
        .ADDRESS(addr_b3), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN(we_b3), .CHIPSELECT(cs_b3), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_3)
    );

    reg [15:0] mux_dout_l;
    always @(*) begin
        if (stereo_d1) begin
            mux_dout_l = r_bank_d1[0] ? bank_dout_1 : bank_dout_0;
        end else begin
            case (r_bank_d1)
                2'd0: mux_dout_l = bank_dout_0;
                2'd1: mux_dout_l = bank_dout_1;
                2'd2: mux_dout_l = bank_dout_2;
                default: mux_dout_l = bank_dout_3;
            endcase
        end
    end

    wire [15:0] mux_dout_r = stereo_d1 ? (r_bank_d1[0] ? bank_dout_3 : bank_dout_2) : mux_dout_l;

    assign scan_rdata_l = mux_dout_l;
    assign scan_rdata_r = mux_dout_r;

    always @(posedge clk_sys or negedge rst_n) begin
        if (!rst_n) begin
            r_bank_d1   <= 2'd0;
            stereo_d1   <= 1'b0;
            scan_rvalid <= 1'b0;
        end else begin
            r_bank_d1   <= r_bank;
            stereo_d1   <= stereo_indep_mode;
            scan_rvalid <= scan_re;
        end
    end

endmodule

`ifndef SYNTHESIS
module SB_SPRAM256KA (
    input  wire [13:0] ADDRESS,
    input  wire [15:0] DATAIN,
    input  wire [3:0]  MASKWREN,
    input  wire        WREN,
    input  wire        CHIPSELECT,
    input  wire        CLOCK,
    input  wire        STANDBY,
    input  wire        SLEEP,
    input  wire        POWEROFF,
    output reg  [15:0] DATAOUT
);
    reg [15:0] mem [0:16383];
    integer k;
    initial begin
        for (k = 0; k < 16384; k = k + 1) mem[k] = 16'h0000;
        DATAOUT = 16'h0000;
    end
    always @(posedge CLOCK) begin
        if (CHIPSELECT && POWEROFF && !SLEEP && !STANDBY) begin
            if (WREN) begin
                if (MASKWREN[0]) mem[ADDRESS][3:0]   <= DATAIN[3:0];
                if (MASKWREN[1]) mem[ADDRESS][7:4]   <= DATAIN[7:4];
                if (MASKWREN[2]) mem[ADDRESS][11:8]  <= DATAIN[11:8];
                if (MASKWREN[3]) mem[ADDRESS][15:12] <= DATAIN[15:12];
            end
            DATAOUT <= mem[ADDRESS];
        end
    end
endmodule
`endif
