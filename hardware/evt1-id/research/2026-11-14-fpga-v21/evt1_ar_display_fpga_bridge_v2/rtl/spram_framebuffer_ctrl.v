// SPDX-License-Identifier: MIT
// Module:   spram_framebuffer_ctrl
// Standard: IEEE 1364-2005 Verilog
// Purpose:  4x SB_SPRAM256KA (128 KiB total) controller with lossless host_ready
//           arbitration and behavioral simulation model for SB_SPRAM256KA.

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module spram_framebuffer_ctrl (
    input  wire        clk_sys,
    input  wire        rst_n,
    // Host Write Port (from Post-CRC Staging Commit Engine)
    output wire        host_ready,
    input  wire        host_we,
    input  wire [15:0] host_waddr,
    input  wire [15:0] host_wdata,
    // Scanline Burst Reader Port
    input  wire        scan_re,
    input  wire [15:0] scan_raddr,
    output wire [15:0] scan_rdata,
    output reg         scan_rvalid
);

    // Scanline fetch (160 clocks per active line) has deterministic priority;
    // host_ready stalls the staging buffer commit engine so ZERO writes are ever lost!
    assign host_ready = ~scan_re;

    wire [15:0] mux_addr = scan_re ? scan_raddr : host_waddr;
    wire [1:0]  bank_sel = mux_addr[15:14];
    wire [13:0] sub_addr = mux_addr[13:0];

    wire [15:0] bank_dout_0, bank_dout_1, bank_dout_2, bank_dout_3;
    reg  [1:0]  bank_sel_d1;

    SB_SPRAM256KA u_spram0 (
        .ADDRESS(sub_addr), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN((bank_sel == 2'd0) && (!scan_re) && host_we),
        .CHIPSELECT(bank_sel == 2'd0), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_0)
    );
    SB_SPRAM256KA u_spram1 (
        .ADDRESS(sub_addr), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN((bank_sel == 2'd1) && (!scan_re) && host_we),
        .CHIPSELECT(bank_sel == 2'd1), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_1)
    );
    SB_SPRAM256KA u_spram2 (
        .ADDRESS(sub_addr), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN((bank_sel == 2'd2) && (!scan_re) && host_we),
        .CHIPSELECT(bank_sel == 2'd2), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_2)
    );
    SB_SPRAM256KA u_spram3 (
        .ADDRESS(sub_addr), .DATAIN(host_wdata), .MASKWREN(4'b1111),
        .WREN((bank_sel == 2'd3) && (!scan_re) && host_we),
        .CHIPSELECT(bank_sel == 2'd3), .CLOCK(clk_sys),
        .STANDBY(1'b0), .SLEEP(1'b0), .POWEROFF(1'b1), .DATAOUT(bank_dout_3)
    );

    reg [15:0] mux_dout;
    always @(*) begin
        case (bank_sel_d1)
            2'd0: mux_dout = bank_dout_0;
            2'd1: mux_dout = bank_dout_1;
            2'd2: mux_dout = bank_dout_2;
            default: mux_dout = bank_dout_3;
        endcase
    end

    always @(posedge clk_sys or negedge rst_n) begin
        if (!rst_n) begin
            bank_sel_d1 <= 2'd0;
            scan_rvalid <= 1'b0;
        end else begin
            bank_sel_d1 <= bank_sel;
            scan_rvalid <= scan_re;
        end
    end

    assign scan_rdata = mux_dout;

endmodule

`ifndef SYNTHESIS
// Behavioral cycle-accurate simulation model of Lattice iCE40UP5K SB_SPRAM256KA (16384 x 16-bit)
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
