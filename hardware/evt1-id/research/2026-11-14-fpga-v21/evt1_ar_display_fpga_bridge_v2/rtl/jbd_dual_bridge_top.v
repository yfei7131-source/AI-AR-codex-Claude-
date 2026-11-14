// SPDX-License-Identifier: MIT
// Module:   jbd_dual_bridge_top
// Standard: IEEE 1364-2005 Verilog
// Purpose:  Top-level EVT-1 Binocular AR Display Bridge FPGA

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module jbd_dual_bridge_top #(
    parameter VBLANK_CLOCKS = 17'd102080
) (
    input  wire       clk_48m_in,
    input  wire       rst_n,
    // ESP32-S3 QSPI Host Interface (40 MHz SCLK)
    input  wire       s3_cs_n,
    input  wire       s3_sclk,
    input  wire [3:0] s3_io,
    // Dual JBD 0.13" Optical Engine QSPI Master Interface (24 MHz SCLK)
    output wire       opt_sclk,
    output wire       opt_cs_l_n,
    output wire       opt_cs_r_n,
    output wire [3:0] opt_l_io,
    output wire [3:0] opt_r_io,
    // Diagnostic / Sync Outputs
    output wire       bridge_crc_err,
    output wire       bridge_cdc_err,
    output wire       vsync_out
);

    wire              spram_host_ready;
    wire              host_we;
    wire [15:0]       host_waddr;
    wire [15:0]       host_wdata;

    wire [1:0]        cfg_mode;
    wire signed [7:0] cfg_disparity_px;
    wire              cfg_mirror_left;
    wire              cfg_mirror_right;
    wire              frame_commit_req;

    wire [7:0]        cmd_lut_waddr;
    wire [7:0]        cmd_lut_wdata;
    wire              cmd_lut_we;

    wire              scan_re;
    wire [15:0]       scan_raddr;
    wire [15:0]       scan_rdata;
    wire              scan_rvalid;

    wire [15:0]       good_cnt, bad_cnt;
    wire              active_front_bank;

    s3_qspi_slave_rx u_s3_rx (
        .clk_sys          (clk_48m_in),
        .rst_n            (rst_n),
        .s3_cs_n          (s3_cs_n),
        .s3_sclk          (s3_sclk),
        .s3_io_in         (s3_io),
        .spram_host_ready (spram_host_ready),
        .spram_we         (host_we),
        .spram_waddr      (host_waddr),
        .spram_wdata      (host_wdata),
        .cfg_mode         (cfg_mode),
        .cfg_disparity_px (cfg_disparity_px),
        .cfg_mirror_left  (cfg_mirror_left),
        .cfg_mirror_right (cfg_mirror_right),
        .frame_commit_req (frame_commit_req),
        .cmd_lut_waddr    (cmd_lut_waddr),
        .cmd_lut_wdata    (cmd_lut_wdata),
        .cmd_lut_we       (cmd_lut_we),
        .crc_error_flag   (bridge_crc_err),
        .cdc_overflow_err (bridge_cdc_err),
        .good_packet_cnt  (good_cnt),
        .bad_packet_cnt   (bad_cnt)
    );

    spram_framebuffer_ctrl u_spram_ctrl (
        .clk_sys     (clk_48m_in),
        .rst_n       (rst_n),
        .host_ready  (spram_host_ready),
        .host_we     (host_we),
        .host_waddr  (host_waddr),
        .host_wdata  (host_wdata),
        .scan_re     (scan_re),
        .scan_raddr  (scan_raddr),
        .scan_rdata  (scan_rdata),
        .scan_rvalid (scan_rvalid)
    );

    binocular_scanline_engine #(
        .VBLANK_CLOCKS(VBLANK_CLOCKS)
    ) u_scan_engine (
        .clk_sys           (clk_48m_in),
        .rst_n             (rst_n),
        .cfg_mode          (cfg_mode),
        .cfg_disparity_px  (cfg_disparity_px),
        .cfg_mirror_left   (cfg_mirror_left),
        .cfg_mirror_right  (cfg_mirror_right),
        .frame_commit_req  (frame_commit_req),
        .cmd_lut_waddr     (cmd_lut_waddr),
        .cmd_lut_wdata     (cmd_lut_wdata),
        .cmd_lut_we        (cmd_lut_we),
        .spram_re          (scan_re),
        .spram_raddr       (scan_raddr),
        .spram_rdata       (scan_rdata),
        .spram_rvalid      (scan_rvalid),
        .opt_sclk          (opt_sclk),
        .opt_cs_l_n        (opt_cs_l_n),
        .opt_cs_r_n        (opt_cs_r_n),
        .opt_l_io          (opt_l_io),
        .opt_r_io          (opt_r_io),
        .vsync_done_pulse  (vsync_out),
        .active_front_bank (active_front_bank)
    );

endmodule
