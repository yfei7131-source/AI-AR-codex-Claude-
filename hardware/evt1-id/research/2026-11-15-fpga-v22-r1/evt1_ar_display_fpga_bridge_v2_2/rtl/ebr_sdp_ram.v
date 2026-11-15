// SPDX-License-Identifier: MIT
// Module:   ebr_sdp_ram
// Standard: IEEE 1364-2005 Verilog
// Purpose:  Canonical Simple Dual-Port (1 Write + 1 Synchronous Read) Block RAM
//           with ZERO asynchronous reset on the memory array. Guarantees 100%
//           deterministic mapping to Lattice iCE40UP5K SB_RAM40_4K EBR primitives
//           in Yosys (`synth_ice40`), preventing DFF/LUT explosion.

`timescale 1ns / 1ps

module ebr_sdp_ram #(
    parameter DATA_WIDTH = 16,
    parameter ADDR_WIDTH = 8
) (
    input  wire                  wr_clk,
    input  wire                  wr_en,
    input  wire [ADDR_WIDTH-1:0] wr_addr,
    input  wire [DATA_WIDTH-1:0] wr_data,
    input  wire                  rd_clk,
    input  wire                  rd_en,
    input  wire [ADDR_WIDTH-1:0] rd_addr,
    output reg  [DATA_WIDTH-1:0] rd_data
);

    reg [DATA_WIDTH-1:0] mem [0:(1<<ADDR_WIDTH)-1];

    always @(posedge wr_clk) begin
        if (wr_en) begin
            mem[wr_addr] <= wr_data;
        end
    end

    always @(posedge rd_clk) begin
        if (rd_en) begin
            rd_data <= mem[rd_addr];
        end
    end

endmodule
