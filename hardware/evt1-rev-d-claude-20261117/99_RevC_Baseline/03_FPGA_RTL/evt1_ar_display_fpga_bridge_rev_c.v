// =============================================================================
// Zhiyuan Yuedong (智元跃动) AI/AR Smart Glasses V1.0 — EVT-1 Rev C
// Module: evt1_ar_display_fpga_bridge_rev_c
// Target: Lattice iCE40UP5K-UWG30ITR (30-Ball WLCSP, 2.11 x 2.54 x 0.45 mm)
//
// Key Architecture & 48.000 MHz (`clk_48m`) Timing-Closure Optimizations:
//   1. Pre-Registered FIFO Non-Empty Flag (`fifo_not_empty_q`):
//      - Eliminates the 9-bit Gray-code equality comparator (`rptr_gray == wptr_gray_s2`)
//        from the `start_ebr_rd` combinational path by registering
//        `fifo_not_empty_q <= ((ebr_rd_phase_q ? rptr_gray_next : rptr_gray) != wptr_gray_s2)`,
//        reducing `start_ebr_rd` to a single 3-input `SB_LUT4`.
//   2. Carry-Chain Co-Located MSB Register (`s1_diff_10_q`) & 2-LUT `s1_do_write`:
//      - In Stage 0 -> Stage 1, the 11-bit row-offset subtractor
//        `s0_diff_hi = s0_addr_q[14:4] - next_row_base_hi_q[10:0]` registers its MSB
//        `s0_diff_hi[10]` directly into the co-located `SB_DFFE` inside the top carry-chain
//        Logic Cell (`s1_diff_10_q <= s0_diff_hi[10]`, 0 post-carry LUTs, 0 post-carry routing),
//        while tapping lower bits into three 4-input LUT flip-flops (`s1_hit_a_q`,
//        `s1_hit_b_q`, `s1_hit_c_q`).
//      - In Stage 1 -> Stage 2, `s1_is_next_row = (!s1_diff_10_q) && s1_hit_a_q && s1_hit_b_q && s1_hit_c_q`
//        is a single 4-input `SB_LUT4`, and `s1_do_write` is a single 4-input `SB_LUT4`
//        (total combinational depth = 2 `SB_LUT4` levels).
//   3. Monotonic Frame-Wide Prefetch Address Counter (`pf_addr_q`):
//      - Eliminates `next_row_base_q[14:0]` (15 flip-flops + 15-bit `+80` adder + 15-bit
//        2:1 load mux on `pf_addr_q`) by holding `pf_addr_q = 15'd0` during VBLANK
//        (`!next_row_valid_q`) and incrementing `pf_addr_q` by +1 during the 80-cycle
//        `prefetch_read_q` window of each active row (`0..19,199` across the 240 rows),
//        mapping directly to 15 pure `SB_CARRY` + `SB_DFFESR` cells with 0 post-carry LUTs.
//   4. 2-Level Balanced XOR Tree for `wptr_bin_dec` & Pruned `rst_n_q` Fanout:
//      - Replaces the ripple XOR loop in `wptr_bin_dec` with an explicit 2-level `SB_LUT4`
//        XOR tree and removes redundant `rst_n_q` resets from zero-initialized telemetry
//        and watermark counters, cutting `rst_n_q` fanout by >70%.
//   5. Pre-Registered `h_cmd_ok_q` & `h_in_bounds_q` in 40 MHz `host_sck` Domain:
//      - Pre-evaluates command decode at nibble 2 and bounds check (`< 0x4B00`) at nibble 7,
//        minimizing combinational setup path on `u_cdc_fifo_*.WE` at nibble 9.
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
    // =========================================================================
    reg [FIFO_ADDR_BITS:0] wptr_bin     = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] wptr_gray    = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_gray_h1 = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_gray_h2 = {(FIFO_ADDR_BITS+1){1'b0}};

    reg [FIFO_ADDR_BITS:0] rptr_bin        = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_gray       = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] wptr_gray_s1    = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] wptr_gray_s2    = {(FIFO_ADDR_BITS+1){1'b0}};
    reg                    fifo_not_empty_q = 1'b0;

    // Verification & Diagnostics Telemetry Registers (Hardware-initialized in CRAM)
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

    // 2. Host QSPI Synchronous Deserializer & Pre-Registered Write Qualification (posedge host_sck)
    reg [7:0]  h_cmd_reg      = 8'h00;
    reg [15:0] h_addr_reg     = 16'h0000;
    reg [15:0] h_data_shift   = 16'h0000;
    reg        h_cmd_ok_q     = 1'b0;
    reg        h_in_bounds_q  = 1'b0;

    wire is_write_cmd    = h_cmd_ok_q;
    wire host_word_valid = (!host_cs_n) && (h_nib_cnt == 4'd9) && h_cmd_ok_q;
    wire host_in_bounds  = h_in_bounds_q;
    wire fifo_we_h       = host_word_valid && h_in_bounds_q && (!fifo_full_h);
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
                4'd2: begin
                    h_addr_reg[15:12] <= host_qio;
                    h_cmd_ok_q        <= (h_cmd_reg[7:2] == 6'b101000);
                end
                4'd3: h_addr_reg[11:8]    <= host_qio;
                4'd4: h_addr_reg[7:4]     <= host_qio;
                4'd5: h_addr_reg[3:0]     <= host_qio;
                4'd6: h_data_shift[15:12] <= host_qio;
                4'd7: begin
                    h_data_shift[11:8] <= host_qio;
                    h_in_bounds_q      <= (h_addr_reg[15:8] < 8'h4B);
                end
                4'd8: h_data_shift[7:4]   <= host_qio;
                4'd9: begin
                    if (h_cmd_ok_q) begin
                        if (h_in_bounds_q) begin
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

    // =========================================================================
    // 3x SB_RAM40_4K Asynchronous CDC FIFO Read Interface
    // RADDR driven directly by flip-flop `rptr_bin[7:0]` (ZERO LUTs on RADDR!)
    // =========================================================================
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
    reg        s1_eye_q       = 1'b0;
    reg [14:0] s1_addr_q      = 15'd0;
    reg [15:0] s1_data_q      = 16'd0;
    reg        s1_diff_10_q   = 1'b0; // Co-located inside MSB carry-chain cell (0 post-carry LUTs!)
    reg        s1_hit_a_q     = 1'b0; // s0_diff_hi[9:6] == 4'd0 (1 LUT4)
    reg        s1_hit_b_q     = 1'b0; // (s0_diff_hi[5:3] == 3'd0) && s0_tear_q (1 LUT4)
    reg        s1_hit_c_q     = 1'b0; // (!s0_diff_hi[2]) || (s0_diff_hi[1:0] == 2'd0) (1 LUT4)

    // 11-bit subtraction on Stage 0 flip-flops (`s0_addr_q[14:4] - next_row_base_hi_q`)
    wire [10:0] s0_diff_hi = s0_addr_q[14:4] - next_row_base_hi_q;

    // 4-input LUT4 combining the 4 Stage-1 match flip-flops
    wire s1_is_next_row   = (!s1_diff_10_q) && s1_hit_a_q && s1_hit_b_q && s1_hit_c_q;
    wire tear_row_holdoff = s1_valid_q && in_tear_guard_win_q && s1_is_next_row;
    wire s1_do_write      = s1_valid_q && (!prefetch_active) && (!(in_tear_guard_win_q && s1_is_next_row));
    wire s1_ready         = (!s1_valid_q) || s1_do_write;
    wire s0_ready         = (!s0_valid_q) || s1_ready;
    wire start_ebr_rd     = fifo_not_empty_q && (!ebr_rd_phase_q) && s0_ready;

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
    // 2x SB_RAM40_4K Ping-Pong Line Buffers (Driven by Monotonic Prefetch & Read Pointers)
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

    // 2-Level Balanced XOR Tree for Gray-to-Binary Occupancy Watermark (Max 2 LUT4 levels)
    wire xor_g8_5 = ^wptr_gray_s2[8:5];
    wire [FIFO_ADDR_BITS:0] wptr_bin_dec = {
        wptr_gray_s2[8],
        ^wptr_gray_s2[8:7],
        ^wptr_gray_s2[8:6],
        xor_g8_5,
        xor_g8_5 ^ wptr_gray_s2[4],
        xor_g8_5 ^ (^wptr_gray_s2[4:3]),
        xor_g8_5 ^ (^wptr_gray_s2[4:2]),
        xor_g8_5 ^ (^wptr_gray_s2[4:1]),
        (^wptr_gray_s2[8:6]) ^ (^wptr_gray_s2[5:3]) ^ (^wptr_gray_s2[2:0])
    };
    reg [FIFO_ADDR_BITS:0] wptr_bin_sync_q = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] rptr_bin_d1     = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0] fifo_level_q    = {(FIFO_ADDR_BITS+1){1'b0}};

    // Shift-Register Pixel Serializer & Pre-registered Header Nibble
    reg [15:0] pix_shift_l  = 16'd0;
    reg [15:0] pix_shift_r  = 16'd0;
    reg [3:0]  hdr_nibble_q = 4'h3;
    reg        in_hdr_win_q = 1'b1;

    // =========================================================================
    // Pure Datapath & Telemetry Pipeline Registers (No `rst_n_q` fanout load)
    // =========================================================================
    always @(posedge clk_48m) begin
        // 1. 3-Stage Pipelined Occupancy Watermark & Telemetry Counters
        wptr_bin_sync_q <= wptr_bin_dec;
        rptr_bin_d1     <= rptr_bin;
        fifo_level_q    <= wptr_bin_sync_q - rptr_bin_d1;
        if (fifo_level_q > fifo_max_level)
            fifo_max_level <= fifo_level_q;

        if (inc_wr_l_q) wr_cnt_l_q <= wr_cnt_l_q + 18'd1;
        if (inc_wr_r_q) wr_cnt_r_q <= wr_cnt_r_q + 18'd1;
        if (inc_tear_q) tear_cnt_q <= tear_cnt_q + 16'd1;

        // 2. Stage 0 datapath capture directly from EBR RDATA (0 LUTs on D, 0 LUTs on E)
        if (ebr_rd_phase_q) begin
            s0_tear_q <= fifo_rdata_ctrl[1];
            s0_eye_q  <= fifo_rdata_ctrl[0];
            s0_addr_q <= fifo_rdata_hi[14:0];
            s0_data_q <= fifo_rdata_lo;
        end

        // 3. Stage 1 datapath capture + carry-chain MSB FF + 4-input LUT4 row-offset decode
        if (s1_ready && s0_valid_q) begin
            s1_eye_q     <= s0_eye_q;
            s1_addr_q    <= s0_addr_q;
            s1_data_q    <= s0_data_q;
            s1_diff_10_q <= s0_diff_hi[10];
            s1_hit_a_q   <= (s0_diff_hi[9:6] == 4'd0);
            s1_hit_b_q   <= (s0_diff_hi[5:3] == 3'd0) && s0_tear_q;
            s1_hit_c_q   <= (!s0_diff_hi[2]) || (s0_diff_hi[1:0] == 2'd0);
        end

        // 4. Stage 2 SPRAM address & write data registers (pure 2:1 mux -> SB_DFF)
        spram_addr_q  <= prefetch_read_q ? pf_addr_q[13:0] : s1_addr_q[13:0];
        spram_wdata_q <= s1_data_q;

        // 5. Monotonic Frame-Wide Prefetch Counters (`0..19,199` across active rows)
        if (!next_row_valid_q)
            pf_addr_q <= 15'd0;
        else if (prefetch_read_q)
            pf_addr_q <= pf_addr_q + 15'd1;

        if (!prefetch_read_q)
            pf_idx_q <= 7'd0;
        else
            pf_idx_q <= pf_idx_q + 7'd1;

        // 6. Prefetch datapath pipeline (SPRAM DATAOUT -> 2:1 mux -> SB_DFF -> EBR WDATA)
        pf_bank_s1    <= pf_addr_q[14];
        pf_waddr_s1   <= {next_row_page_q, pf_idx_q};
        pf_bank_s2    <= pf_bank_s1;
        pf_waddr_s2   <= pf_waddr_s1;
        ebr_waddr_q   <= pf_waddr_s2;
        ebr_wdata_l_q <= pf_bank_s2 ? spram_dout_l1 : spram_dout_l0;
        ebr_wdata_r_q <= pf_bank_s2 ? spram_dout_r1 : spram_dout_r0;

        // 7. Pixel shift-register serializer (2:1 mux on EBR RDATA -> SB_DFFE)
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
            fifo_not_empty_q    <= 1'b0;
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
            // 1. 2-FF Gray-code write pointer sync + Pre-registered FIFO non-empty flag
            wptr_gray_s1     <= wptr_gray;
            wptr_gray_s2     <= wptr_gray_s1;
            fifo_not_empty_q <= ((ebr_rd_phase_q ? rptr_gray_next : rptr_gray) != wptr_gray_s1);

            // 2. Pipelined Telemetry Enable Pulses
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

            // 5. Prefetch Valid Pipeline
            pf_valid_s1 <= prefetch_read_q;
            pf_valid_s2 <= pf_valid_s1;
            ebr_we_q    <= pf_valid_s2;

            // 6. Frame/Line Counters & Pre-Registered Row Base Accumulator
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
                end else if (row_cnt == (V_ACTIVE - 2)) begin
                    next_row_q         <= 9'd240;
                    next_row_valid_q   <= 1'b0;
                    next_row_page_q    <= 1'b0;
                end else begin
                    next_row_q <= next_row_q + 9'd1;
                    if (next_row_valid_q) begin
                        next_row_page_q    <= ~next_row_page_q;
                        next_row_base_hi_q <= next_row_base_hi_q + 11'd5;
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
            if (col_last_q)
                frame_vsync_1v8 <= row_last_q;
            else if (col_cnt == 11'd47)
                frame_vsync_1v8 <= 1'b0;

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
