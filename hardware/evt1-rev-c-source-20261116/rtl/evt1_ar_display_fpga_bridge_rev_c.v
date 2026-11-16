// =============================================================================
// Zhiyuan Yuedong (智元跃动) AI/AR Smart Glasses V1.0 — EVT-1 Rev C (PR #19 P0 Fixed)
// Module: evt1_ar_display_fpga_bridge_rev_c
// Target: Lattice iCE40UP5K-UWG30ITR (30-Ball WLCSP, 2.11 x 2.54 x 0.45 mm)
//
// P0 Fixes Implemented (On top of 43f2960979ff):
//   1. True Active-Scanout Anti-Tearing Holdoff (`tear_row_holdoff`) + 256-Word EBR FIFO:
//      - Instantiates 3x Lattice `SB_RAM40_4K` hard macros (`u_cdc_fifo_ctrl`,
//        `u_cdc_fifo_hi`, `u_cdc_fifo_lo`, FIFO_ADDR_BITS = 8, DEPTH = 256 words)
//        storing per-word `{wr_tear_sync_q, wr_eye_q, wr_addr_q[15:0], wr_data_q[15:0]}`.
//      - During active scanout rows `row_cnt = 0..238` (where `next_row = 1..239 < V_ACTIVE`
//        triggers a real line prefetch at `col_cnt = 1800..1881`), if a tear-guarded
//        write (`0xA2/0xA3`, `wr_tear_sync_q == 1`) targets `next_row` (`next_row_base_addr
//        .. next_row_base_addr + 79`) within the pre-prefetch danger window
//        `col_cnt = 1400..1881` (`in_tear_guard_win`), `tear_row_holdoff` holds off
//        draining into `SB_SPRAM256KA` until `col_cnt == 1882` (at most 482 clks =
//        10.04 us, accumulating at most 101 words in the 256-word EBR FIFO -> 0 overflow!).
//      - Consequently, `prefetch_active` (`col_cnt = 1800..1881`) prefetches 100% of
//        the intact old `next_row` into `u_ebr_l/r` (ZERO mid-line tearing on `next_row`),
//        and at `col_cnt == 1882` the held-off new words drain at 48 Mwords/s into
//        `SB_SPRAM256KA` for the subsequent frame!
//   2. Ping-Pong EBR Line Buffer Pages (`Page 0: 0..79`, `Page 1: 128..207`) inside
//      `u_ebr_l` and `u_ebr_r` so prefetching `next_row` never overwrites `cur_row`.
//   3. Clean Yosys `synth_ice40` & Strict IEEE 1364-2005 Syntax.
// =============================================================================

`timescale 1ns / 1ps

module evt1_ar_display_fpga_bridge_rev_c #(
    parameter integer H_ACTIVE        = 320,
    parameter integer V_ACTIVE        = 240,
    parameter integer VBLANK_LINES    = 160,
    parameter integer BPP             = 4,
    parameter integer CMD_HDR_NIBBLES = 12,
    parameter integer CLKS_PER_LINE   = 2000,
    parameter integer FIFO_ADDR_BITS  = 8
) (
    // 1. System Clock Input (1 pin: Ball B3 IOT_46B_G0)
    input  wire        clk_48m,

    // 2. Host Quad-SPI Slave Interface (6 pins: Bank 1 D1, C1, E1, F1, F2, B1)
    input  wire        host_sck,
    input  wire        host_cs_n,
    input  wire [3:0]  host_qio,

    // 3. Shared Lockstep Binocular QSPI Clock & CS_N (2 pins: Bank 2 E3, C3)
    output reg         opt_sck,
    output reg         opt_cs_n,

    // 4. Left Optical Engine Independent 4-bit QSPI Data (4 pins: A1, A2, A4, E4)
    output reg  [3:0]  opt_l_qdo,

    // 5. Right Optical Engine Independent 4-bit QSPI Data (4 pins: E5, D5, F5, F4)
    output reg  [3:0]  opt_r_qdo,

    // 6. Hardware Frame Sync Output to IMU FSYNC & Host (1 pin: Ball D3 IOB_12A_G4_CDONE)
    output reg         frame_vsync_1v8
);
    // Total top-level ports = 1 + 6 + 2 + 4 + 4 + 1 = 18 standard CMOS PIO balls!

    localparam integer PIXEL_NIBBLES_PER_LINE = (H_ACTIVE * BPP) / 4; // 320 nibbles
    localparam integer TOTAL_NIBBLES_PER_LINE = CMD_HDR_NIBBLES + PIXEL_NIBBLES_PER_LINE; // 332 nibbles
    localparam integer ACTIVE_SCAN_CLKS       = TOTAL_NIBBLES_PER_LINE * 2; // 664 clks @ 48MHz (24MHz opt_sck)
    localparam integer WORDS_PER_LINE         = (H_ACTIVE * BPP) / 16; // 80 words (16-bit) per line
    localparam integer MAX_FB_WORDS           = V_ACTIVE * WORDS_PER_LINE; // 19,200 words (0x0000..0x4AFF)
    localparam integer PREFETCH_GUARD_CLK     = 1400; // 400 clks (8.33 us) before prefetch_active starts
    localparam integer PREFETCH_START_CLK     = 1800; // Prefetch next row from SPRAM into EBR during [1800..1881]
    localparam integer PREFETCH_END_CLK       = PREFETCH_START_CLK + WORDS_PER_LINE + 2; // 1882
    localparam integer TOTAL_LINES            = V_ACTIVE + VBLANK_LINES; // 400 lines (800,000 clks = 60.000 Hz)
    localparam integer FIFO_DEPTH             = (1 << FIFO_ADDR_BITS); // 256 words deep (via 3x SB_RAM40_4K)

    // =========================================================================
    // Power-On Reset Generator (Synthesizable 4-bit counter after CRAM wakeup)
    // =========================================================================
    reg [3:0] por_cnt = 4'h0;
    wire      rst_n   = &por_cnt;
    always @(posedge clk_48m) begin
        if (!rst_n)
            por_cnt <= por_cnt + 4'd1;
    end

    // =========================================================================
    // 256-Word x 34-Bit Dual-Clock Gray-Code EBR Asynchronous CDC FIFO
    // Backed by 3x Lattice SB_RAM40_4K Hard Macros:
    //   - `u_cdc_fifo_ctrl` : {14'd0, tear_sync_mode[0], eye_sel[0]}
    //   - `u_cdc_fifo_hi`   : word_addr[15:0] (0x0000..0x4AFF)
    //   - `u_cdc_fifo_lo`   : pixel_data[15:0]
    //   Commands supported:
    //     0xA0 : Immediate Write Left Eye SPRAM     (eye_sel=0, tear_sync=0)
    //     0xA1 : Immediate Write Right Eye SPRAM    (eye_sel=1, tear_sync=0)
    //     0xA2 : Tear-Guarded Write Left Eye SPRAM  (eye_sel=0, tear_sync=1)
    //     0xA3 : Tear-Guarded Write Right Eye SPRAM (eye_sel=1, tear_sync=1)
    // =========================================================================
    reg [FIFO_ADDR_BITS:0] wptr_bin     = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] wptr_gray    = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_gray_h1 = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_gray_h2 = {(FIFO_ADDR_BITS+1){1'b0}};

    reg [FIFO_ADDR_BITS:0] rptr_bin     = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_gray    = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] wptr_gray_s1 = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] wptr_gray_s2 = {(FIFO_ADDR_BITS+1){1'b0}};

    // Verification & Diagnostics Telemetry Registers
    reg                    fifo_overflow_sticky = 1'b0;
    reg [15:0]             boundary_err_cnt     = 16'd0;
    reg [31:0]             words_written_l      = 32'd0;
    reg [31:0]             words_written_r      = 32'd0;
    reg [FIFO_ADDR_BITS:0] fifo_max_level       = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [31:0]             tear_hazard_cnt      = 32'd0;

    wire [FIFO_ADDR_BITS:0] wptr_bin_next  = wptr_bin + 1'b1;
    wire [FIFO_ADDR_BITS:0] wptr_gray_next = (wptr_bin_next >> 1) ^ wptr_bin_next;
    wire                    fifo_full_h    = (wptr_gray == {~rptr_gray_h2[FIFO_ADDR_BITS:FIFO_ADDR_BITS-1],
                                                             rptr_gray_h2[FIFO_ADDR_BITS-2:0]});

    // 1. Packet Nibble Counter (ONLY register with async reset on posedge host_cs_n)
    reg [3:0] h_nib_cnt = 4'd0;
    always @(posedge host_sck or posedge host_cs_n) begin
        if (host_cs_n) begin
            h_nib_cnt <= 4'd0;
        end else begin
            if (h_nib_cnt == 4'd9)
                h_nib_cnt <= 4'd6;
            else
                h_nib_cnt <= h_nib_cnt + 4'd1;
        end
    end

    // 2. Host QSPI Synchronous Deserializer & Write Pointer Update (pure posedge host_sck)
    reg [7:0]  h_cmd_reg    = 8'h00;
    reg [15:0] h_addr_reg   = 16'h0000;
    reg [15:0] h_data_shift = 16'h0000;

    wire is_write_cmd    = (h_cmd_reg == 8'hA0) || (h_cmd_reg == 8'hA1) ||
                           (h_cmd_reg == 8'hA2) || (h_cmd_reg == 8'hA3);
    wire host_word_valid = (!host_cs_n) && (h_nib_cnt == 4'd9) && is_write_cmd;
    wire host_in_bounds  = (h_addr_reg < MAX_FB_WORDS);
    wire fifo_we_h       = host_word_valid && host_in_bounds && (!fifo_full_h);
    wire [15:0] fifo_wdata_ctrl = {14'd0, h_cmd_reg[1], h_cmd_reg[0]};
    wire [15:0] fifo_wdata_hi   = h_addr_reg;
    wire [15:0] fifo_wdata_lo   = {h_data_shift[15:4], host_qio};

    always @(posedge host_sck) begin
        rptr_gray_h1 <= rptr_gray;
        rptr_gray_h2 <= rptr_gray_h1;

        if (!host_cs_n) begin
            case (h_nib_cnt)
                4'd0: h_cmd_reg[7:4]      <= host_qio;
                4'd1: h_cmd_reg[3:0]      <= host_qio;
                4'd2: h_addr_reg[15:12]   <= host_qio;
                4'd3: h_addr_reg[11:8]    <= host_qio;
                4'd4: h_addr_reg[7:4]     <= host_qio;
                4'd5: h_addr_reg[3:0]     <= host_qio;
                4'd6: h_data_shift[15:12] <= host_qio;
                4'd7: h_data_shift[11:8]  <= host_qio;
                4'd8: h_data_shift[7:4]   <= host_qio;
                4'd9: begin
                    if (is_write_cmd) begin
                        if (host_in_bounds) begin
                            if (!fifo_full_h) begin
                                wptr_bin  <= wptr_bin_next;
                                wptr_gray <= wptr_gray_next;
                            end else begin
                                fifo_overflow_sticky <= 1'b1;
                            end
                        end else begin
                            boundary_err_cnt <= boundary_err_cnt + 16'd1;
                        end
                        h_addr_reg <= h_addr_reg + 16'd1;
                    end
                end
                default: ;
            endcase
        end
    end

    // =========================================================================
    // Scanout Timing Counters (2000 clks/line x 400 lines = 800,000 clks = 60.000 Hz)
    // Initializes row_cnt to 9'd240 (start of VBLANK) on reset so Row 0
    // is prefetched at row_cnt==399 before Frame 0 Row 0 scanout starts.
    // Note: Active rows are 0..239. `next_row < V_ACTIVE` is TRUE on:
    //   - row_cnt == 399 (next_row == 0)
    //   - row_cnt == 0..238 (next_row == 1..239)
    //   (On row_cnt == 239, next_row == 240, entering VBLANK -> no prefetch)
    // =========================================================================
    reg [10:0] col_cnt = 11'd0;
    reg [8:0]  row_cnt = 9'd240;

    wire in_active_rows  = (row_cnt < V_ACTIVE);
    wire in_qspi_burst   = in_active_rows && (col_cnt < ACTIVE_SCAN_CLKS);
    wire in_prefetch_win = (col_cnt >= PREFETCH_START_CLK) && (col_cnt < PREFETCH_END_CLK);
    wire [8:0] next_row  = (row_cnt == TOTAL_LINES - 1) ? 9'd0 : (row_cnt + 9'd1);
    wire prefetch_active = in_prefetch_win && (next_row < V_ACTIVE);

    // =========================================================================
    // Read-Side CDC FIFO Synchronizer & Bounded Tear-Guard SPRAM Arbiter (clk_48m)
    // =========================================================================
    wire                    fifo_empty_c   = (rptr_gray == wptr_gray_s2);
    wire [FIFO_ADDR_BITS:0] rptr_bin_next  = rptr_bin + 1'b1;
    wire [FIFO_ADDR_BITS:0] rptr_gray_next = (rptr_bin_next >> 1) ^ rptr_bin_next;

    wire [15:0] fifo_rdata_ctrl;
    wire [15:0] fifo_rdata_hi;
    wire [15:0] fifo_rdata_lo;

    wire        wr_tear_sync_q = fifo_rdata_ctrl[1];
    wire        wr_eye_q       = fifo_rdata_ctrl[0];
    wire [15:0] wr_addr_q      = fifo_rdata_hi;
    wire [15:0] wr_data_q      = fifo_rdata_lo;

    // Shift-add computation for next_row * 80 = (next_row << 6) + (next_row << 4)
    wire [15:0] next_row_base_addr = ({1'b0, next_row, 6'd0}) + ({3'b0, next_row, 4'd0});

    // Bounded Pre-Prefetch Tear-Guard Holdoff:
    // If a tear-guarded write (0xA2/0xA3) targets `next_row` during `col_cnt = 1400..1881`
    // when `next_row < V_ACTIVE` is about to be (or is being) prefetched into EBR,
    // hold off draining into SPRAM until `col_cnt == 1882` (max 482 clks = 10.04 us =
    // max 101 words buffered in the 256-word EBR FIFO -> 0 overflow & 0 mid-line tear!).
    wire in_tear_guard_win = (next_row < V_ACTIVE) &&
                             (col_cnt >= PREFETCH_GUARD_CLK) && (col_cnt < PREFETCH_END_CLK);
    wire tear_row_holdoff  = (!fifo_empty_c) && wr_tear_sync_q && in_tear_guard_win &&
                             (wr_addr_q >= next_row_base_addr) &&
                             (wr_addr_q < (next_row_base_addr + WORDS_PER_LINE));

    wire spram_do_write = (!fifo_empty_c) && (!prefetch_active) && (!tear_row_holdoff);

    // Lookahead read address for SB_RAM40_4K synchronous read ports
    wire [7:0] fifo_ebr_raddr = spram_do_write ? rptr_bin_next[7:0] : rptr_bin[7:0];

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_cdc_fifo_ctrl (
        .RDATA (fifo_rdata_ctrl),
        .RADDR ({3'd0, fifo_ebr_raddr}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({3'd0, wptr_bin[7:0]}),
        .WCLK  (host_sck),
        .WCLKE (1'b1),
        .WDATA (fifo_wdata_ctrl),
        .WE    (fifo_we_h),
        .MASK  (16'h0000)
    );

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_cdc_fifo_hi (
        .RDATA (fifo_rdata_hi),
        .RADDR ({3'd0, fifo_ebr_raddr}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({3'd0, wptr_bin[7:0]}),
        .WCLK  (host_sck),
        .WCLKE (1'b1),
        .WDATA (fifo_wdata_hi),
        .WE    (fifo_we_h),
        .MASK  (16'h0000)
    );

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_cdc_fifo_lo (
        .RDATA (fifo_rdata_lo),
        .RADDR ({3'd0, fifo_ebr_raddr}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({3'd0, wptr_bin[7:0]}),
        .WCLK  (host_sck),
        .WCLKE (1'b1),
        .WDATA (fifo_wdata_lo),
        .WE    (fifo_we_h),
        .MASK  (16'h0000)
    );

    // Decode synchronized wptr_gray_s2 to binary for FIFO occupancy telemetry
    integer g_i;
    reg [FIFO_ADDR_BITS:0] wptr_bin_sync;
    always @(*) begin
        wptr_bin_sync[FIFO_ADDR_BITS] = wptr_gray_s2[FIFO_ADDR_BITS];
        for (g_i = FIFO_ADDR_BITS - 1; g_i >= 0; g_i = g_i - 1)
            wptr_bin_sync[g_i] = wptr_bin_sync[g_i + 1] ^ wptr_gray_s2[g_i];
    end
    wire [FIFO_ADDR_BITS:0] fifo_level_c = wptr_bin_sync - rptr_bin;

    // =========================================================================
    // SPRAM Address & Control Multiplexer (4x SB_SPRAM256KA = 1024 Kibit)
    // Each eye uses 19,200 16-bit words (0x0000..0x4AFF):
    //   - Bank 0 (addr[14] == 0): words 0..16383  (0x0000..0x3FFF)
    //   - Bank 1 (addr[14] == 1): words 16384..19199 (0x4000..0x4AFF)
    // =========================================================================
    wire [6:0]  prefetch_word_idx   = col_cnt - PREFETCH_START_CLK;
    wire [15:0] prefetch_spram_addr = next_row_base_addr + {9'd0, prefetch_word_idx};

    wire [15:0] spram_mux_addr = prefetch_active ? prefetch_spram_addr : wr_addr_q;
    wire        spram_bank_sel = spram_mux_addr[14];

    wire spram_wren_l0 = spram_do_write && (!wr_eye_q) && (!spram_bank_sel);
    wire spram_wren_l1 = spram_do_write && (!wr_eye_q) && ( spram_bank_sel);
    wire spram_wren_r0 = spram_do_write && ( wr_eye_q) && (!spram_bank_sel);
    wire spram_wren_r1 = spram_do_write && ( wr_eye_q) && ( spram_bank_sel);

    wire [15:0] spram_dout_l0, spram_dout_l1;
    wire [15:0] spram_dout_r0, spram_dout_r1;
    reg         spram_rd_bank_d1 = 1'b0;

    wire [15:0] spram_dout_l = spram_rd_bank_d1 ? spram_dout_l1 : spram_dout_l0;
    wire [15:0] spram_dout_r = spram_rd_bank_d1 ? spram_dout_r1 : spram_dout_r0;

    // Instantiate 4x Lattice iCE40 UltraPlus 256Kibit Single-Port RAM Hard Macros
    SB_SPRAM256KA u_spram_l0 (
        .ADDRESS   (spram_mux_addr[13:0]),
        .DATAIN    (wr_data_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_l0),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_l0)
    );

    SB_SPRAM256KA u_spram_l1 (
        .ADDRESS   (spram_mux_addr[13:0]),
        .DATAIN    (wr_data_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_l1),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_l1)
    );

    SB_SPRAM256KA u_spram_r0 (
        .ADDRESS   (spram_mux_addr[13:0]),
        .DATAIN    (wr_data_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_r0),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_r0)
    );

    SB_SPRAM256KA u_spram_r1 (
        .ADDRESS   (spram_mux_addr[13:0]),
        .DATAIN    (wr_data_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_r1),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_r1)
    );

    // =========================================================================
    // Instantiate 2x Lattice SB_RAM40_4K EBR Dual-Port Line Buffers (Left & Right)
    // Uses Ping-Pong Pages inside each 256-word EBR (Page 0: 0..79, Page 1: 128..207)
    // so prefetch of `next_row` never overwrites `cur_row`!
    // =========================================================================
    reg        prefetch_valid_d1 = 1'b0;
    reg [6:0]  prefetch_idx_d1   = 7'd0;
    wire       active_ebr_page   = row_cnt[0];
    wire       prefetch_ebr_page = next_row[0];

    wire [9:0]  nibble_idx_in_line = (col_cnt >> 1) - CMD_HDR_NIBBLES;
    wire [6:0]  ebr_word_idx = (col_cnt < (CMD_HDR_NIBBLES * 2 - 2)) ? 7'd0 : ((nibble_idx_in_line + 10'd1) >> 2);
    wire [7:0]  ebr_raddr    = {active_ebr_page, ebr_word_idx};
    wire [7:0]  ebr_waddr    = {prefetch_ebr_page, prefetch_idx_d1};
    wire [15:0] ebr_rdata_l;
    wire [15:0] ebr_rdata_r;

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_ebr_l (
        .RDATA (ebr_rdata_l),
        .RADDR ({3'd0, ebr_raddr}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({3'd0, ebr_waddr}),
        .WCLK  (clk_48m),
        .WCLKE (1'b1),
        .WDATA (spram_dout_l),
        .WE    (prefetch_valid_d1),
        .MASK  (16'h0000)
    );

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_ebr_r (
        .RDATA (ebr_rdata_r),
        .RADDR ({3'd0, ebr_raddr}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({3'd0, ebr_waddr}),
        .WCLK  (clk_48m),
        .WCLKE (1'b1),
        .WDATA (spram_dout_r),
        .WE    (prefetch_valid_d1),
        .MASK  (16'h0000)
    );

    // Select current nibble (MSB first: bits [15:12], [11:8], [7:4], [3:0])
    wire [1:0] nib_sel = nibble_idx_in_line[1:0];
    reg  [3:0] pix_nib_l;
    reg  [3:0] pix_nib_r;

    always @(*) begin
        case (nib_sel)
            2'd0: begin pix_nib_l = ebr_rdata_l[15:12]; pix_nib_r = ebr_rdata_r[15:12]; end
            2'd1: begin pix_nib_l = ebr_rdata_l[11:8];  pix_nib_r = ebr_rdata_r[11:8];  end
            2'd2: begin pix_nib_l = ebr_rdata_l[7:4];   pix_nib_r = ebr_rdata_r[7:4];   end
            2'd3: begin pix_nib_l = ebr_rdata_l[3:0];   pix_nib_r = ebr_rdata_r[3:0];   end
        endcase
    end

    // Header nibble generator: 8'h32 (Quad Page Write) + 16-bit row_cnt + 24-bit 0
    wire [3:0] hdr_nib_idx = col_cnt[4:1];
    reg  [3:0] hdr_nibble;
    always @(*) begin
        case (hdr_nib_idx)
            4'd0: hdr_nibble = 4'h3;
            4'd1: hdr_nibble = 4'h2;
            4'd2: hdr_nibble = 4'h0;
            4'd3: hdr_nibble = {3'b000, row_cnt[8]};
            4'd4: hdr_nibble = row_cnt[7:4];
            4'd5: hdr_nibble = row_cnt[3:0];
            default: hdr_nibble = 4'h0;
        endcase
    end

    // =========================================================================
    // Main Synchronous Scanout & Pipeline FSM (clk_48m)
    // =========================================================================
    always @(posedge clk_48m) begin
        if (!rst_n) begin
            wptr_gray_s1      <= {(FIFO_ADDR_BITS+1){1'b0}};
            wptr_gray_s2      <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_bin          <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_gray         <= {(FIFO_ADDR_BITS+1){1'b0}};
            words_written_l   <= 32'd0;
            words_written_r   <= 32'd0;
            fifo_max_level    <= {(FIFO_ADDR_BITS+1){1'b0}};
            tear_hazard_cnt   <= 32'd0;
            col_cnt           <= 11'd0;
            row_cnt           <= 9'd240; // Start at VBLANK Line 240 so Row 0 prefetches at Line 399
            spram_rd_bank_d1  <= 1'b0;
            prefetch_valid_d1 <= 1'b0;
            prefetch_idx_d1   <= 7'd0;
            opt_sck           <= 1'b0;
            opt_cs_n          <= 1'b1;
            opt_l_qdo         <= 4'h0;
            opt_r_qdo         <= 4'h0;
            frame_vsync_1v8   <= 1'b0;
        end else begin
            // 1. 2-FF Gray-code write pointer synchronization into clk_48m domain
            wptr_gray_s1 <= wptr_gray;
            wptr_gray_s2 <= wptr_gray_s1;

            if (fifo_level_c > fifo_max_level)
                fifo_max_level <= fifo_level_c;

            // 2. Drain Async EBR CDC FIFO into SPRAM (holds off on next_row during col_cnt 1400..1881)
            if (spram_do_write) begin
                rptr_bin  <= rptr_bin_next;
                rptr_gray <= rptr_gray_next;
                if (!wr_eye_q)
                    words_written_l <= words_written_l + 32'd1;
                else
                    words_written_r <= words_written_r + 32'd1;
            end else if (tear_row_holdoff) begin
                tear_hazard_cnt <= tear_hazard_cnt + 32'd1;
            end

            // 3. Advance 2000x400 frame counters (exact 800,000 clks/frame = 60.000 Hz)
            if (col_cnt == CLKS_PER_LINE - 1) begin
                col_cnt <= 11'd0;
                if (row_cnt == TOTAL_LINES - 1)
                    row_cnt <= 9'd0;
                else
                    row_cnt <= row_cnt + 9'd1;
            end else begin
                col_cnt <= col_cnt + 11'd1;
            end

            // 4. Pipeline SPRAM -> EBR line prefetch during [1800..1879]
            spram_rd_bank_d1  <= spram_bank_sel;
            prefetch_valid_d1 <= prefetch_active && (prefetch_word_idx < WORDS_PER_LINE);
            prefetch_idx_d1   <= prefetch_word_idx;

            // 5. Hardware VSYNC pulse (Row 0, Col 0..47 -> exact 1.000 us pulse @ 60.000 Hz)
            frame_vsync_1v8 <= (row_cnt == 9'd0) && (col_cnt < 11'd48);

            // 6. 24.000 MHz QSPI Master Serializer (Even cycle: SCK=0 & setup data; Odd cycle: SCK=1 sample)
            if (in_qspi_burst) begin
                opt_cs_n <= 1'b0;
                if (col_cnt[0] == 1'b0) begin
                    opt_sck <= 1'b0;
                    if (col_cnt < (CMD_HDR_NIBBLES * 2)) begin
                        opt_l_qdo <= hdr_nibble;
                        opt_r_qdo <= hdr_nibble;
                    end else begin
                        opt_l_qdo <= pix_nib_l;
                        opt_r_qdo <= pix_nib_r;
                    end
                end else begin
                    opt_sck <= 1'b1; // Rising edge of 24 MHz QSPI clock: data held stable!
                end
            end else begin
                opt_cs_n  <= 1'b1;
                opt_sck   <= 1'b0;
                opt_l_qdo <= 4'h0;
                opt_r_qdo <= 4'h0;
            end
        end
    end

endmodule
