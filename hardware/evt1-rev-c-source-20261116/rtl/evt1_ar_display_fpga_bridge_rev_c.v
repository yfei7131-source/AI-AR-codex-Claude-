// =============================================================================
// Zhiyuan Yuedong (智元跃动) AI/AR Smart Glasses V1.0 — EVT-1 Rev C (PR #19 CI Timing & Sim Fixed)
// Module: evt1_ar_display_fpga_bridge_rev_c
// Target: Lattice iCE40UP5K-UWG30ITR (30-Ball WLCSP, 2.11 x 2.54 x 0.45 mm)
//
// P0 Fixes Implemented (On top of 43f2960979ff & 8697069):
//   1. Deeply Pipelined 48.000 MHz (`clk_48m`) Datapath & Control for >60 MHz STA Closure:
//      - Decoupled 3x `SB_RAM40_4K` CDC FIFO read ports (`RADDR = {3'd0, rptr_bin[7:0]}`,
//        0 LUTs on `RADDR`) from `SB_SPRAM256KA` and tear-guard comparators via a
//        3-stage registered pipeline:
//          * Stage 0 (`s0_*`): Captures `u_cdc_fifo_*.RDATA` directly into pure `SB_DFFE`
//            registers (`0` LUT levels on `RDATA`).
//          * Stage 1 (`s1_*`): Computes the 11-bit row-offset subtraction
//            `s0_addr_q[14:4] - next_row_base_hi_q[10:0]` (exploiting `80 = 5 * 16` so
//            `next_row_base[3:0] == 4'b0000`) and pre-decodes `0 <= diff_hi < 5` into
//            three 1-bit flip-flops (`s1_hit_a_q`, `s1_hit_b_q`, `s1_hit_c_q`).
//          * Stage 2 (`spram_*_q`): Drives all four corner `SB_SPRAM256KA` hard macros
//            (`ADDRESS[13:0]`, `DATAIN[15:0]`, `WREN`) directly from dedicated flip-flops
//            with ZERO combinational logic on the hard-macro input pins.
//      - Registered `SB_SPRAM256KA.DATAOUT` bank mux into `ebr_wdata_l_q` / `ebr_wdata_r_q`
//        flip-flops before writing to `u_ebr_l` / `u_ebr_r`.
//      - Replaced the combinational 10-bit subtractor/adder chain `(col_cnt >> 1) - 12`
//        on `u_ebr_l/r.RADDR` and `RDATA` with a registered `ebr_raddr_q[7:0]` counter and
//        16-bit shift registers (`pix_shift_l`, `pix_shift_r`), reducing EBR `RDATA` load
//        to a single 2:1 `SB_LUT4` mux.
//      - Replaced combinational `next_row * 80` shift-add and 11-bit window magnitude
//        comparators with once-per-line registered accumulators (`next_row_base_q`,
//        `next_row_base_hi_q`) and cycle-exact equality set/clear window flip-flops
//        (`in_qspi_burst_q`, `in_tear_guard_win_q`, `prefetch_active`, `prefetch_read_q`).
//      - Pipelined Gray-to-Binary FIFO occupancy watermark (`wptr_bin_sync_q` ->
//        `fifo_level_q` -> `fifo_max_level`) across 3 register stages.
//   2. Preserves 256-Word EBR FIFO (`3x SB_RAM40_4K`), Binocular Independent Framebuffers
//      (`4x SB_SPRAM256KA` + `2x SB_RAM40_4K`), Exact 60.000 Hz (`800,000 clks`), and
//      Active-Scanout Pre-Prefetch Anti-Tearing Holdoff (`tear_row_holdoff`).
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
    localparam integer PREFETCH_GUARD_CLK     = 1400; // 400 clks (8.33 us) before prefetch starts
    localparam integer PREFETCH_START_CLK     = 1800; // Prefetch next row from SPRAM into EBR during [1800..1879]
    localparam integer PREFETCH_END_CLK       = PREFETCH_START_CLK + WORDS_PER_LINE + 4; // 1884 (covers 3-stage pipeline)
    localparam integer TOTAL_LINES            = V_ACTIVE + VBLANK_LINES; // 400 lines (800,000 clks = 60.000 Hz)
    localparam integer FIFO_DEPTH             = (1 << FIFO_ADDR_BITS); // 256 words deep (via 3x SB_RAM40_4K)

    // =========================================================================
    // Power-On Reset Generator (Synthesizable 4-bit counter + registered rst_n_q)
    // =========================================================================
    reg [3:0] por_cnt = 4'h0;
    reg       rst_n_q = 1'b0;
    always @(posedge clk_48m) begin
        if (&por_cnt)
            rst_n_q <= 1'b1;
        else
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
    reg [17:0]             wr_cnt_l_q           = 18'd0;
    reg [17:0]             wr_cnt_r_q           = 18'd0;
    reg [15:0]             tear_cnt_q           = 16'd0;
    reg                    inc_wr_l_q           = 1'b0;
    reg                    inc_wr_r_q           = 1'b0;
    reg                    inc_tear_q           = 1'b0;
    wire [31:0]            words_written_l      = {14'd0, wr_cnt_l_q};
    wire [31:0]            words_written_r      = {14'd0, wr_cnt_r_q};
    wire [31:0]            tear_hazard_cnt      = {16'd0, tear_cnt_q};
    reg [FIFO_ADDR_BITS:0] fifo_max_level       = {(FIFO_ADDR_BITS+1){1'b0}};

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

    // 0xA0..0xA3 share upper 6 bits 6'b1010_00; 19,200 = 16'h4B00 has 8'h00 low byte
    wire is_write_cmd    = (h_cmd_reg[7:2] == 6'b101000);
    wire host_word_valid = (!host_cs_n) && (h_nib_cnt == 4'd9) && is_write_cmd;
    wire host_in_bounds  = (h_addr_reg[15:8] < 8'h4B);
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
    // Scanout Timing Counters & Pre-Registered Window Flags (clk_48m)
    // =========================================================================
    reg [10:0] col_cnt             = 11'd0;
    reg [8:0]  row_cnt             = 9'd240;
    reg        col_last_q          = 1'b0;
    reg        row_last_q          = 1'b0;
    reg        in_active_rows_q    = 1'b0;
    reg        in_qspi_burst_q     = 1'b0;
    reg        in_tear_guard_win_q = 1'b0;
    reg        prefetch_active     = 1'b0;
    reg        prefetch_read_q     = 1'b0;

    reg [8:0]  next_row_q          = 9'd241;
    reg        next_row_valid_q    = 1'b0;
    reg        next_row_page_q     = 1'b1;
    reg [10:0] next_row_base_hi_q  = 11'd0; // (next_row * 80) >> 4 = next_row * 5
    reg [14:0] next_row_base_q     = 15'd0; // next_row * 80

    // =========================================================================
    // 3x SB_RAM40_4K Asynchronous CDC FIFO Read Interface
    // RADDR driven directly by flip-flop `rptr_bin[7:0]` (ZERO LUTs on RADDR!)
    // =========================================================================
    wire                    fifo_empty_c   = (rptr_gray == wptr_gray_s2);
    wire [FIFO_ADDR_BITS:0] rptr_bin_next  = rptr_bin + 1'b1;
    wire [FIFO_ADDR_BITS:0] rptr_gray_next = (rptr_bin_next >> 1) ^ rptr_bin_next;

    wire [15:0] fifo_rdata_ctrl;
    wire [15:0] fifo_rdata_hi;
    wire [15:0] fifo_rdata_lo;

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_cdc_fifo_ctrl (
        .RDATA (fifo_rdata_ctrl),
        .RADDR ({3'd0, rptr_bin[7:0]}),
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
        .RADDR ({3'd0, rptr_bin[7:0]}),
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
        .RADDR ({3'd0, rptr_bin[7:0]}),
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

    // =========================================================================
    // 3-Stage Pipelined FIFO Drain, Tear-Guard Check & Registered SPRAM Drive
    // =========================================================================
    reg        ebr_rd_phase_q = 1'b0;
    reg        s0_valid_q     = 1'b0;
    reg        s0_tear_q      = 1'b0;
    reg        s0_eye_q       = 1'b0;
    reg [14:0] s0_addr_q      = 15'd0;
    reg [15:0] s0_data_q      = 16'd0;

    reg        s1_valid_q     = 1'b0;
    reg        s1_tear_q      = 1'b0;
    reg        s1_eye_q       = 1'b0;
    reg [14:0] s1_addr_q      = 15'd0;
    reg [15:0] s1_data_q      = 16'd0;
    reg        s1_hit_a_q     = 1'b0;
    reg        s1_hit_b_q     = 1'b0;
    reg        s1_hit_c_q     = 1'b0;

    // 11-bit subtraction on Stage 0 flip-flops (`s0_addr_q[14:4] - next_row_base_hi_q`)
    wire [10:0] s0_diff_hi = s0_addr_q[14:4] - next_row_base_hi_q;

    wire s1_is_next_row   = s1_hit_a_q && s1_hit_b_q && s1_hit_c_q;
    wire tear_row_holdoff = s1_valid_q && s1_tear_q && in_tear_guard_win_q && s1_is_next_row;
    wire s1_do_write      = s1_valid_q && (!prefetch_active) && (!tear_row_holdoff);
    wire s1_ready         = (!s1_valid_q) || s1_do_write;
    wire s0_ready         = (!s0_valid_q) || s1_ready;
    wire start_ebr_rd     = (!fifo_empty_c) && (!ebr_rd_phase_q) && s0_ready;

    // Stage 2: Dedicated Flip-Flops Driving 4x SB_SPRAM256KA Directly (0 LUTs on SPRAM inputs!)
    reg [13:0] spram_addr_q    = 14'd0;
    reg [15:0] spram_wdata_q   = 16'd0;
    reg        spram_wren_l0_q = 1'b0;
    reg        spram_wren_l1_q = 1'b0;
    reg        spram_wren_r0_q = 1'b0;
    reg        spram_wren_r1_q = 1'b0;

    wire [15:0] spram_dout_l0, spram_dout_l1;
    wire [15:0] spram_dout_r0, spram_dout_r1;

    SB_SPRAM256KA u_spram_l0 (
        .ADDRESS   (spram_addr_q),
        .DATAIN    (spram_wdata_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_l0_q),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_l0)
    );

    SB_SPRAM256KA u_spram_l1 (
        .ADDRESS   (spram_addr_q),
        .DATAIN    (spram_wdata_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_l1_q),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_l1)
    );

    SB_SPRAM256KA u_spram_r0 (
        .ADDRESS   (spram_addr_q),
        .DATAIN    (spram_wdata_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_r0_q),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_r0)
    );

    SB_SPRAM256KA u_spram_r1 (
        .ADDRESS   (spram_addr_q),
        .DATAIN    (spram_wdata_q),
        .MASKWREN  (4'b1111),
        .WREN      (spram_wren_r1_q),
        .CHIPSELECT(1'b1),
        .CLOCK     (clk_48m),
        .STANDBY   (1'b0),
        .SLEEP     (1'b0),
        .POWEROFF  (1'b1),
        .DATAOUT   (spram_dout_r1)
    );

    // =========================================================================
    // 2x SB_RAM40_4K Ping-Pong Line Buffers (Driven by Registered Prefetch & Read Pointers)
    // =========================================================================
    reg [14:0] pf_addr_q     = 15'd0;
    reg [6:0]  pf_idx_q      = 7'd0;
    reg        pf_valid_s1   = 1'b0;
    reg        pf_bank_s1    = 1'b0;
    reg [7:0]  pf_waddr_s1   = 8'd0;
    reg        pf_valid_s2   = 1'b0;
    reg        pf_bank_s2    = 1'b0;
    reg [7:0]  pf_waddr_s2   = 8'd0;

    reg        ebr_we_q      = 1'b0;
    reg [7:0]  ebr_waddr_q   = 8'd0;
    reg [15:0] ebr_wdata_l_q = 16'd0;
    reg [15:0] ebr_wdata_r_q = 16'd0;
    reg [7:0]  ebr_raddr_q   = 8'd0;

    wire [15:0] ebr_rdata_l;
    wire [15:0] ebr_rdata_r;

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_ebr_l (
        .RDATA (ebr_rdata_l),
        .RADDR ({3'd0, ebr_raddr_q}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({3'd0, ebr_waddr_q}),
        .WCLK  (clk_48m),
        .WCLKE (1'b1),
        .WDATA (ebr_wdata_l_q),
        .WE    (ebr_we_q),
        .MASK  (16'h0000)
    );

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_ebr_r (
        .RDATA (ebr_rdata_r),
        .RADDR ({3'd0, ebr_raddr_q}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({3'd0, ebr_waddr_q}),
        .WCLK  (clk_48m),
        .WCLKE (1'b1),
        .WDATA (ebr_wdata_r_q),
        .WE    (ebr_we_q),
        .MASK  (16'h0000)
    );

    // 3-Stage Pipelined Gray-to-Binary Occupancy Watermark
    integer g_i;
    reg [FIFO_ADDR_BITS:0] wptr_bin_dec;
    always @(*) begin
        wptr_bin_dec[FIFO_ADDR_BITS] = wptr_gray_s2[FIFO_ADDR_BITS];
        for (g_i = FIFO_ADDR_BITS - 1; g_i >= 0; g_i = g_i - 1)
            wptr_bin_dec[g_i] = wptr_bin_dec[g_i + 1] ^ wptr_gray_s2[g_i];
    end
    reg [FIFO_ADDR_BITS:0] wptr_bin_sync_q = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_bin_d1     = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] fifo_level_q    = {(FIFO_ADDR_BITS+1){1'b0}};

    // Shift-Register Pixel Serializer & Pre-registered Header Nibble
    reg [15:0] pix_shift_l  = 16'd0;
    reg [15:0] pix_shift_r  = 16'd0;
    reg [3:0]  hdr_nibble_q = 4'h3;
    reg        in_hdr_win_q = 1'b1;

    // =========================================================================
    // Pure Datapath Pipeline Registers (NO synchronous reset -> pure SB_DFF / SB_DFFE)
    // =========================================================================
    always @(posedge clk_48m) begin
        // Stage 0 datapath capture directly from EBR RDATA (0 LUTs on D, 0 LUTs on E)
        if (ebr_rd_phase_q) begin
            s0_tear_q <= fifo_rdata_ctrl[1];
            s0_eye_q  <= fifo_rdata_ctrl[0];
            s0_addr_q <= fifo_rdata_hi[14:0];
            s0_data_q <= fifo_rdata_lo;
        end

        // Stage 1 datapath capture + 11-bit row-offset pre-decode
        if (s1_ready && s0_valid_q) begin
            s1_tear_q  <= s0_tear_q;
            s1_eye_q   <= s0_eye_q;
            s1_addr_q  <= s0_addr_q;
            s1_data_q  <= s0_data_q;
            s1_hit_a_q <= (s0_diff_hi[10:7] == 4'd0);
            s1_hit_b_q <= (s0_diff_hi[6:3]  == 4'd0);
            s1_hit_c_q <= (!s0_diff_hi[2]) || (s0_diff_hi[1:0] == 2'd0);
        end

        // Stage 2 SPRAM address & write data registers (pure 2:1 mux -> SB_DFF)
        spram_addr_q  <= prefetch_read_q ? pf_addr_q[13:0] : s1_addr_q[13:0];
        spram_wdata_q <= s1_data_q;

        // Prefetch datapath pipeline (SPRAM DATAOUT -> 2:1 mux -> SB_DFF -> EBR WDATA)
        pf_bank_s1    <= pf_addr_q[14];
        pf_waddr_s1   <= {next_row_page_q, pf_idx_q};
        pf_bank_s2    <= pf_bank_s1;
        pf_waddr_s2   <= pf_waddr_s1;
        ebr_waddr_q   <= pf_waddr_s2;
        ebr_wdata_l_q <= pf_bank_s2 ? spram_dout_l1 : spram_dout_l0;
        ebr_wdata_r_q <= pf_bank_s2 ? spram_dout_r1 : spram_dout_r0;

        // Pixel shift-register serializer (2:1 mux on EBR RDATA -> SB_DFFE)
        if ((~col_cnt[0]) | (col_cnt[2] & col_cnt[1])) begin
            pix_shift_l <= col_cnt[0] ? ebr_rdata_l : {pix_shift_l[11:0], 4'h0};
            pix_shift_r <= col_cnt[0] ? ebr_rdata_r : {pix_shift_r[11:0], 4'h0};
        end
    end

    // =========================================================================
    // Main Synchronous Control & Timing FSM (clk_48m)
    // =========================================================================
    always @(posedge clk_48m) begin
        if (!rst_n_q) begin
            wptr_gray_s1        <= {(FIFO_ADDR_BITS+1){1'b0}};
            wptr_gray_s2        <= {(FIFO_ADDR_BITS+1){1'b0}};
            wptr_bin_sync_q     <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_bin_d1         <= {(FIFO_ADDR_BITS+1){1'b0}};
            fifo_level_q        <= {(FIFO_ADDR_BITS+1){1'b0}};
            fifo_max_level      <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_bin            <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_gray           <= {(FIFO_ADDR_BITS+1){1'b0}};
            ebr_rd_phase_q      <= 1'b0;
            s0_valid_q          <= 1'b0;
            s1_valid_q          <= 1'b0;
            spram_wren_l0_q     <= 1'b0;
            spram_wren_l1_q     <= 1'b0;
            spram_wren_r0_q     <= 1'b0;
            spram_wren_r1_q     <= 1'b0;
            inc_wr_l_q          <= 1'b0;
            inc_wr_r_q          <= 1'b0;
            inc_tear_q          <= 1'b0;
            wr_cnt_l_q          <= 18'd0;
            wr_cnt_r_q          <= 18'd0;
            tear_cnt_q          <= 16'd0;
            col_cnt             <= 11'd0;
            row_cnt             <= 9'd240;
            col_last_q          <= 1'b0;
            row_last_q          <= 1'b0;
            in_active_rows_q    <= 1'b0;
            in_qspi_burst_q     <= 1'b0;
            in_tear_guard_win_q <= 1'b0;
            prefetch_active     <= 1'b0;
            prefetch_read_q     <= 1'b0;
            next_row_q          <= 9'd241;
            next_row_valid_q    <= 1'b0;
            next_row_page_q     <= 1'b1;
            next_row_base_hi_q  <= 11'd0;
            next_row_base_q     <= 15'd0;
            pf_addr_q           <= 15'd0;
            pf_idx_q            <= 7'd0;
            pf_valid_s1         <= 1'b0;
            pf_valid_s2         <= 1'b0;
            ebr_we_q            <= 1'b0;
            ebr_raddr_q         <= 8'd0;
            hdr_nibble_q        <= 4'h3;
            in_hdr_win_q        <= 1'b1;
            opt_sck             <= 1'b0;
            opt_cs_n            <= 1'b1;
            opt_l_qdo           <= 4'h0;
            opt_r_qdo           <= 4'h0;
            frame_vsync_1v8     <= 1'b0;
        end else begin
            // 1. 2-FF Gray-code write pointer sync + 3-stage pipelined occupancy watermark
            wptr_gray_s1    <= wptr_gray;
            wptr_gray_s2    <= wptr_gray_s1;
            wptr_bin_sync_q <= wptr_bin_dec;
            rptr_bin_d1     <= rptr_bin;
            fifo_level_q    <= wptr_bin_sync_q - rptr_bin_d1;
            if (fifo_level_q > fifo_max_level)
                fifo_max_level <= fifo_level_q;

            // 2. Pipelined Telemetry Counters (0 LUTs on counter clock-enable!)
            if (inc_wr_l_q) wr_cnt_l_q <= wr_cnt_l_q + 18'd1;
            if (inc_wr_r_q) wr_cnt_r_q <= wr_cnt_r_q + 18'd1;
            if (inc_tear_q) tear_cnt_q <= tear_cnt_q + 16'd1;

            inc_wr_l_q <= s1_do_write && (!s1_eye_q);
            inc_wr_r_q <= s1_do_write && ( s1_eye_q);
            inc_tear_q <= tear_row_holdoff;

            // 3. Stage 2 SPRAM Write-Enable Flip-Flops
            spram_wren_l0_q <= s1_do_write && (!s1_eye_q) && (!s1_addr_q[14]);
            spram_wren_l1_q <= s1_do_write && (!s1_eye_q) && ( s1_addr_q[14]);
            spram_wren_r0_q <= s1_do_write && ( s1_eye_q) && (!s1_addr_q[14]);
            spram_wren_r1_q <= s1_do_write && ( s1_eye_q) && ( s1_addr_q[14]);

            // 4. Stage 1 & Stage 0 Valid Handshake
            if (s1_ready)
                s1_valid_q <= s0_valid_q;

            if (ebr_rd_phase_q) begin
                ebr_rd_phase_q <= 1'b0;
                s0_valid_q     <= 1'b1;
                rptr_bin       <= rptr_bin_next;
                rptr_gray      <= rptr_gray_next;
            end else begin
                if (s1_ready && s0_valid_q)
                    s0_valid_q <= 1'b0;
                if (start_ebr_rd)
                    ebr_rd_phase_q <= 1'b1;
            end

            // 5. Prefetch Valid Pipeline & Address Counter
            pf_valid_s1 <= prefetch_read_q;
            pf_valid_s2 <= pf_valid_s1;
            ebr_we_q    <= pf_valid_s2;

            if (col_cnt == (PREFETCH_START_CLK - 1)) begin
                pf_addr_q <= next_row_base_q;
                pf_idx_q  <= 7'd0;
            end else if (prefetch_read_q) begin
                pf_addr_q <= pf_addr_q + 15'd1;
                pf_idx_q  <= pf_idx_q + 7'd1;
            end

            // 6. Frame/Line Counters & Pre-Registered Row Base Accumulators
            if (col_last_q) begin
                col_cnt    <= 11'd0;
                col_last_q <= 1'b0;
                if (row_last_q) begin
                    row_cnt          <= 9'd0;
                    row_last_q       <= 1'b0;
                    in_active_rows_q <= 1'b1;
                end else begin
                    row_cnt          <= row_cnt + 9'd1;
                    row_last_q       <= (row_cnt == (TOTAL_LINES - 2));
                    if (row_cnt == (V_ACTIVE - 1))
                        in_active_rows_q <= 1'b0;
                end

                if (row_cnt == (TOTAL_LINES - 2)) begin
                    next_row_q         <= 9'd0;
                    next_row_valid_q   <= 1'b1;
                    next_row_page_q    <= 1'b0;
                    next_row_base_hi_q <= 11'd0;
                    next_row_base_q    <= 15'd0;
                end else if (row_cnt == (V_ACTIVE - 2)) begin
                    next_row_q         <= 9'd240;
                    next_row_valid_q   <= 1'b0;
                    next_row_page_q    <= 1'b0;
                end else begin
                    next_row_q <= next_row_q + 9'd1;
                    if (next_row_valid_q) begin
                        next_row_page_q    <= ~next_row_page_q;
                        next_row_base_hi_q <= next_row_base_hi_q + 11'd5;
                        next_row_base_q    <= next_row_base_q + 15'd80;
                    end
                end
            end else begin
                col_cnt    <= col_cnt + 11'd1;
                col_last_q <= (col_cnt == (CLKS_PER_LINE - 2));
            end

            // 7. Cycle-Exact Equality Set/Clear Window Flip-Flops
            if (col_last_q)
                in_qspi_burst_q <= next_row_valid_q;
            else if (col_cnt == (ACTIVE_SCAN_CLKS - 1))
                in_qspi_burst_q <= 1'b0;

            if (col_cnt == (PREFETCH_GUARD_CLK - 1))
                in_tear_guard_win_q <= next_row_valid_q;
            else if (col_cnt == (PREFETCH_END_CLK - 3))
                in_tear_guard_win_q <= 1'b0;

            if (col_cnt == (PREFETCH_START_CLK - 1)) begin
                prefetch_active <= next_row_valid_q;
                prefetch_read_q <= next_row_valid_q;
            end else begin
                if (col_cnt == (PREFETCH_START_CLK + WORDS_PER_LINE - 1))
                    prefetch_read_q <= 1'b0;
                if (col_cnt == (PREFETCH_END_CLK - 1))
                    prefetch_active <= 1'b0;
            end

            // 8. Hardware VSYNC Pulse (Row 0, Col 0..47 -> exact 1.000 us pulse @ 60.000 Hz)
            frame_vsync_1v8 <= (row_cnt == 9'd0) && (col_cnt < 11'd48);

            // 9. EBR Line-Buffer Read Address & Pre-computed Header Nibble
            if (in_hdr_win_q && ((!col_cnt[4]) || (!col_cnt[2]))) begin
                ebr_raddr_q <= {row_cnt[0], 7'd0};
            end else if (in_qspi_burst_q && (col_cnt[2:0] == 3'd6)) begin
                ebr_raddr_q <= {row_cnt[0], ebr_raddr_q[6:0] + 7'd1};
            end

            if (col_last_q) begin
                in_hdr_win_q <= 1'b1;
                hdr_nibble_q <= 4'h3;
            end else begin
                if (col_cnt == (CMD_HDR_NIBBLES * 2 - 1))
                    in_hdr_win_q <= 1'b0;
                if (in_hdr_win_q && col_cnt[0]) begin
                    case (col_cnt[4:1])
                        4'd0: hdr_nibble_q <= 4'h2;
                        4'd1: hdr_nibble_q <= 4'h0;
                        4'd2: hdr_nibble_q <= {3'b000, row_cnt[8]};
                        4'd3: hdr_nibble_q <= row_cnt[7:4];
                        4'd4: hdr_nibble_q <= row_cnt[3:0];
                        default: hdr_nibble_q <= 4'h0;
                    endcase
                end
            end

            // 10. 24.000 MHz QSPI Master Serializer (2:1 mux between hdr_nibble_q & pix_shift[15:12])
            if (in_qspi_burst_q) begin
                opt_cs_n <= 1'b0;
                if (!col_cnt[0]) begin
                    opt_sck   <= 1'b0;
                    opt_l_qdo <= in_hdr_win_q ? hdr_nibble_q : pix_shift_l[15:12];
                    opt_r_qdo <= in_hdr_win_q ? hdr_nibble_q : pix_shift_r[15:12];
                end else begin
                    opt_sck <= 1'b1;
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
