// SPDX-License-Identifier: MIT
// Module:   jbd_dual_bridge_top
// Standard: IEEE 1364-2005 Verilog
// Purpose:  Top-level EVT-1 Binocular AR Display Bridge FPGA (V2.2)
//           Supports bidirectional `s3_io[3:0]` for `OP_READ_STATUS (0x50)` status readback.

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module jbd_dual_bridge_top #(
    parameter VBLANK_CLOCKS = 17'd102080
) (
    input  wire       clk_48m_in,
    input  wire       rst_n,
    input  wire       s3_cs_n,
    input  wire       s3_sclk,
    inout  wire [3:0] s3_io,
    output wire       opt_sclk,
    output wire       opt_cs_l_n,
    output wire       opt_cs_r_n,
    output wire [3:0] opt_l_io,
    output wire [3:0] opt_r_io,
    output wire       bridge_crc_err,
    output wire       bridge_cdc_err,
    output wire       vsync_out
);

    wire [3:0]        s3_io_in = s3_io;
    wire [3:0]        s3_io_out;
    wire              s3_io_oe;
    assign s3_io = (s3_io_oe && !s3_cs_n) ? s3_io_out : 4'bzzzz;

    wire              spram_host_ready;
    wire              active_front_bank;
    wire              stereo_indep_mode;
    wire [1:0]        act_mode_status;
    wire              commit_pending_status;
    wire              host_we;
    wire [15:0]       host_waddr;
    wire [15:0]       host_wdata;

    wire [1:0]        cfg_mode;
    wire signed [7:0] cfg_disparity_px;
    wire              cfg_mirror_left;
    wire              cfg_mirror_right;
    wire              frame_commit_req;
    wire              commit_swap_en;

    wire [7:0]        cmd_lut_waddr;
    wire [7:0]        cmd_lut_wdata;
    wire              cmd_lut_we;

    wire              scan_re;
    wire [15:0]       scan_raddr;
    wire [15:0]       scan_rdata_l;
    wire [15:0]       scan_rdata_r;
    wire              scan_rvalid;

    wire              cdc_fifo_err;
    wire              stage_ovf_err;
    wire [15:0]       good_cnt, bad_cnt;

    assign bridge_cdc_err = cdc_fifo_err | stage_ovf_err;

    s3_qspi_slave_rx u_s3_rx (
        .clk_sys               (clk_48m_in),
        .rst_n                 (rst_n),
        .s3_cs_n               (s3_cs_n),
        .s3_sclk               (s3_sclk),
        .s3_io_in              (s3_io_in),
        .s3_io_out             (s3_io_out),
        .s3_io_oe              (s3_io_oe),
        .spram_host_ready      (spram_host_ready),
        .active_front_bank     (active_front_bank),
        .stereo_indep_mode     (stereo_indep_mode),
        .act_mode_status       (act_mode_status),
        .commit_pending_status (commit_pending_status),
        .spram_we              (host_we),
        .spram_waddr           (host_waddr),
        .spram_wdata           (host_wdata),
        .cfg_mode              (cfg_mode),
        .cfg_disparity_px      (cfg_disparity_px),
        .cfg_mirror_left       (cfg_mirror_left),
        .cfg_mirror_right      (cfg_mirror_right),
        .frame_commit_req      (frame_commit_req),
        .commit_swap_en        (commit_swap_en),
        .cmd_lut_waddr         (cmd_lut_waddr),
        .cmd_lut_wdata         (cmd_lut_wdata),
        .cmd_lut_we            (cmd_lut_we),
        .crc_error_flag        (bridge_crc_err),
        .cdc_overflow_err      (cdc_fifo_err),
        .stage_overflow_err    (stage_ovf_err),
        .good_packet_cnt       (good_cnt),
        .bad_packet_cnt        (bad_cnt)
    );

    spram_framebuffer_ctrl u_spram_ctrl (
        .clk_sys           (clk_48m_in),
        .rst_n             (rst_n),
        .stereo_indep_mode (stereo_indep_mode),
        .host_ready        (spram_host_ready),
        .host_we           (host_we),
        .host_waddr        (host_waddr),
        .host_wdata        (host_wdata),
        .scan_re           (scan_re),
        .scan_raddr        (scan_raddr),
        .scan_rdata_l      (scan_rdata_l),
        .scan_rdata_r      (scan_rdata_r),
        .scan_rvalid       (scan_rvalid)
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
        .commit_swap_en    (commit_swap_en),
        .cmd_lut_waddr     (cmd_lut_waddr),
        .cmd_lut_wdata     (cmd_lut_wdata),
        .cmd_lut_we        (cmd_lut_we),
        .spram_re          (scan_re),
        .spram_raddr       (scan_raddr),
        .spram_rdata_l     (scan_rdata_l),
        .spram_rdata_r     (scan_rdata_r),
        .spram_rvalid      (scan_rvalid),
        .opt_sclk          (opt_sclk),
        .opt_cs_l_n        (opt_cs_l_n),
        .opt_cs_r_n        (opt_cs_r_n),
        .opt_l_io          (opt_l_io),
        .opt_r_io          (opt_r_io),
        .vsync_done_pulse  (vsync_out),
        .active_front_bank (active_front_bank),
        .stereo_indep_mode (stereo_indep_mode),
        .act_mode          (act_mode_status),
        .commit_pending    (commit_pending_status)
    );

endmodule
