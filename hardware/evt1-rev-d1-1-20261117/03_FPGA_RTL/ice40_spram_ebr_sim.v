// =============================================================================
// Behavioral Simulation Models for Lattice iCE40 UltraPlus Hard Macros
//   - SB_SPRAM256KA (16384 x 16-bit Single-Port SRAM = 256 Kibit)
//   - SB_RAM40_4K   (256 x 16-bit Dual-Port Embedded Block RAM = 4 Kibit)
// Used for standard IEEE 1364-2005 Verilog simulation (iverilog / verilator)
// =============================================================================

`timescale 1ns / 1ps

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
    integer i;
    initial begin
        for (i = 0; i < 16384; i = i + 1)
            mem[i] = 16'h0000;
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

module SB_RAM40_4K #(
    parameter integer WRITE_MODE = 0,
    parameter integer READ_MODE  = 0
) (
    output reg  [15:0] RDATA,
    input  wire [10:0] RADDR,
    input  wire        RCLK,
    input  wire        RCLKE,
    input  wire        RE,
    input  wire [10:0] WADDR,
    input  wire        WCLK,
    input  wire        WCLKE,
    input  wire [15:0] WDATA,
    input  wire        WE,
    input  wire [15:0] MASK
);
    reg [15:0] bram [0:255];
    integer k;
    initial begin
        for (k = 0; k < 256; k = k + 1)
            bram[k] = 16'h0000;
        RDATA = 16'h0000;
    end

    always @(posedge WCLK) begin
        if (WCLKE && WE) begin
            bram[WADDR[7:0]] <= (bram[WADDR[7:0]] & MASK) | (WDATA & ~MASK);
        end
    end

    always @(posedge RCLK) begin
        if (RCLKE && RE) begin
            RDATA <= bram[RADDR[7:0]];
        end
    end
endmodule
