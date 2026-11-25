// =============================================================================
// Zhiyuan Yuedong (智元跃动) AI/AR Smart Glasses V1.0 — EVT-1 Rev D1.1 (PR21 baseline)
// Module: evt1_ar_display_fpga_bridge_rev_c   (file/module name kept for CI continuity)
//
// Rev D1.1 safety delta (interface, framebuffer and RAW format retained):
//   - OFF asserts directly from host clock domain even if clk_48m has stopped.
//   - Async-assert / two-clock synchronized release holds OFF until clk_48m runs.
//   - Power OFF clamps optical outputs to SCK=0, CS_N=1, DATA=0 and clears SCAN_EN.
//     An active transaction may be truncated by shutdown; that is a fault abort,
//     not a valid panel transaction. Re-arm requires power and a later scan command.
//   - D3 remains active-low. Independent external liveness/power supervision is
//     still required: user RTL cannot detect its own stopped clock or model hard
//     CDONE/CRESET_B behavior while the FPGA is unconfigured or unpowered.
//
// Rev D changes (all Rev C datapath/timing-closure logic is retained unchanged):
//   D1. Ball D3 (IOB_12A_G4_CDONE) is now ACTIVE-LOW `cdone_vsync_n`: idle HIGH, 1.000 us LOW
//       pulse per frame. During configuration the hard CDONE function holds D3 LOW; after
//       wake-up the user FF (power-up value 0, output inverted) holds D3 HIGH. D3 therefore is
//       HIGH in idle user mode. This level alone does not prove a running clock.
//       Rev D1.1 replaces the old DC RC gate with independent heartbeat qualification,
//       timeout and supply/reset supervision; see the authoritative D1.1 board netlist.
//   D2. Host command 0xA4 = OPT_CTRL (single data word, bits in last nibble):
//         bit0 SCAN_EN      (power-up 0: optical QSPI held idle until host finishes JBD init)
//         bit1 OPT_PWR_REQ  (power-up 1: 0 asynchronously inhibits D3 and optical outputs)
//         bit2 RAW_ARM      (requires power ON and SCAN_EN already 0 before this write)
//         bit3 reserved (write 0)
//   D3. One-shot RAW pass-through window for vendor init (BLK-JBD-02): after an accepted
//       RAW_ARM, the NEXT host CS_N transaction is mirrored combinationally to BOTH eyes
//       (opt_sck=host_sck, opt_cs_n=host_cs_n, opt_l/r_qdo=host_qio). Window state changes
//       only on host_cs_n rising edges, when host_sck and the idle scan outputs are both low,
//       so the mux switch is glitch-free. Decode of 0xA0..0xA4 is suppressed inside the
//       window. No JBD command content is assumed here; ESP32 firmware supplies it after NDA.
//   D4. opt_cs_n is generated as ~opt_cs_q (FF power-up value 0 -> CS deasserted from the
//       first user-mode cycle, independent of yosys init-value handling).
//
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
    output wire        opt_sck,
    output wire        opt_cs_n,

    // 4. Left Optical Engine Independent 4-bit QSPI Data (4 pins: A1, A2, A4, E4)
    output wire [3:0]  opt_l_qdo,

    // 5. Right Optical Engine Independent 4-bit QSPI Data (4 pins: E5, D5, F5, F4)
    output wire [3:0]  opt_r_qdo,

    // 6. Rev D: active-low CDONE/frame-sync to U6_OPT_AVDD RC gate, IMU FSYNC & host GPIO21
    //    (1 pin: Ball D3 IOB_12A_G4_CDONE). Idle HIGH, 1.000 us LOW pulse per 60.000 Hz frame.
    output wire        cdone_vsync_n
);
    // Total top-level ports = 1 + 6 + 2 + 4 + 4 + 1 = 18 standard CMOS PIO balls (unchanged in Rev D)

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
    localparam [7:0]   CMD_OPT_CTRL           = 8'hA4; // Rev D optical control word

    // =========================================================================
    // Rev D: registered scan outputs (clk_48m) + host-domain optical control
    // =========================================================================
    reg        opt_sck_q      = 1'b0;
    reg        opt_cs_q       = 1'b0;  // active-HIGH internal CS; pin = ~opt_cs_q
    reg  [3:0] opt_l_q        = 4'h0;
    reg  [3:0] opt_r_q        = 4'h0;
    reg        vsync_pulse_q  = 1'b0;  // Rev C frame_vsync timing (row 0, col 0..47)
    reg        d3_low_q       = 1'b0;  // 1 => drive Ball D3 LOW (power-up 0 => D3 HIGH)

    reg        opt_scan_en_h  = 1'b0;  // host_sck domain, power-up: scan disabled
    reg        opt_pwr_off_h  = 1'b0;  // host_sck domain, power-up: optics power allowed
    reg        raw_req_tgl_h  = 1'b0;  // host_sck domain, toggles on accepted RAW_ARM
    reg        raw_ack_tgl_c  = 1'b0;  // host_cs_n-rise domain
    reg        raw_window_q   = 1'b0;  // host_cs_n-rise domain: 1 => mirror next transaction

    reg  [1:0] scan_en_sync   = 2'b00; // 2-FF synchronizers into clk_48m
    reg  [1:0] pwr_off_sync   = 2'b00;
    reg        hb_rearm_q     = 1'b0;  // initial configured startup is unchanged; OFF arms heartbeat requalification
    reg        scan_line_en_q = 1'b0;  // enables at line start only, disables immediately
    wire       opt_pwr_inhibit = opt_pwr_off_h | pwr_off_sync[1] | hb_rearm_q;

    // RAW window is (re)evaluated only on host_cs_n rising edges (host_sck idle LOW and the
    // scan outputs idle because RAW_ARM requires SCAN_EN==0 beforehand).
    always @(posedge host_cs_n) begin
        raw_window_q  <= (!opt_pwr_inhibit) && (raw_req_tgl_h != raw_ack_tgl_c);
        raw_ack_tgl_c <= raw_req_tgl_h;
    end

    assign opt_sck       = opt_pwr_inhibit ? 1'b0 : (raw_window_q ? host_sck  : opt_sck_q);
    assign opt_cs_n      = opt_pwr_inhibit ? 1'b1 : (raw_window_q ? host_cs_n : ~opt_cs_q);
    assign opt_l_qdo     = opt_pwr_inhibit ? 4'h0 : (raw_window_q ? host_qio  : opt_l_q);
    assign opt_r_qdo     = opt_pwr_inhibit ? 4'h0 : (raw_window_q ? host_qio  : opt_r_q);
    assign cdone_vsync_n = ~(d3_low_q | opt_pwr_inhibit);

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
    reg        h_ctrl_ok_q    = 1'b0;  // Rev D: 0xA4 OPT_CTRL decoded at nibble 2
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
                    h_cmd_ok_q        <= (h_cmd_reg[7:2] == 6'b101000) && (!raw_window_q);
                    h_ctrl_ok_q       <= (h_cmd_reg == CMD_OPT_CTRL)  && (!raw_window_q);
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
                    // Rev D OPT_CTRL: applied once per CS_N window (first data word only)
                    if (h_ctrl_ok_q) begin
                        h_ctrl_ok_q   <= 1'b0;
                        // ICD: flag bit3 is reserved and must be zero. Consume
                        // the first word even when malformed, so extra data in
                        // this CS window cannot retry or bypass the rejection.
                        // RAW remains opaque because h_ctrl_ok_q is suppressed
                        // at header decode while raw_window_q is active.
                        if (!host_qio[3]) begin
                            opt_scan_en_h <= host_qio[0] && host_qio[1];
                            opt_pwr_off_h <= ~host_qio[1];
                            if (host_qio[1] && host_qio[2] && (!host_qio[0]) && (!opt_scan_en_h))
                                raw_req_tgl_h <= ~raw_req_tgl_h;
                        end
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
    // Rev D1.1: a shutdown does not depend on the clock being supervised.
    // Assertion sets both stages. Deassertion must traverse two real clk_48m
    // edges, including OFF->ON commands received while that clock is stopped.
    always @(posedge clk_48m or posedge opt_pwr_off_h) begin
        if (opt_pwr_off_h)
            pwr_off_sync <= 2'b11;
        else
            pwr_off_sync <= {pwr_off_sync[0], 1'b0};
    end

    // Rev D1.1 re-arm must not turn a host OFF->ON transition into a synthetic
    // frame edge. Hold D3 LOW until the running frame generator has produced a
    // genuine VSYNC pulse. d3_low_q keeps D3 LOW through that pulse's end.
    // Stuck-LOW VSYNC cannot re-arm; stuck-HIGH VSYNC cannot release D3 HIGH.
    always @(posedge clk_48m or posedge opt_pwr_off_h) begin
        if (opt_pwr_off_h)
            hb_rearm_q <= 1'b1;
        else if ((!pwr_off_sync[1]) && vsync_pulse_q)
            hb_rearm_q <= 1'b0;
    end

    always @(posedge clk_48m) begin
        // 0. Rev D: scan control synchronizer (host_sck-domain bit)
        scan_en_sync <= {scan_en_sync[0], opt_scan_en_h};

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
            opt_sck_q           <= 1'b0;
            opt_cs_q            <= 1'b0;
            opt_l_q             <= 4'h0;
            opt_r_q             <= 4'h0;
            vsync_pulse_q       <= 1'b0;
            d3_low_q            <= 1'b0;
            scan_line_en_q      <= 1'b0;
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
            //    Rev D: Ball D3 = ~(pulse | power-off request) -> active-low, DC-high idle.
            if (col_last_q)
                vsync_pulse_q <= row_last_q;
            else if (col_cnt == 11'd47)
                vsync_pulse_q <= 1'b0;
            d3_low_q <= vsync_pulse_q | pwr_off_sync[1];

            // 8b. Rev D scan gating: enable only at a line boundary, disable immediately
            if ((!scan_en_sync[1]) || hb_rearm_q)
                scan_line_en_q <= 1'b0;
            else if (col_last_q)
                scan_line_en_q <= 1'b1;

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
            //     Rev D: gated by scan_line_en_q (OPT_CTRL.SCAN_EN, line-aligned)
            // Do not briefly unmask a frozen serializer as the OFF synchronizer
            // releases; scan synchronization must also be live and enabled.
            if (in_qspi_burst_q && scan_line_en_q && scan_en_sync[1] && (!pwr_off_sync[1])) begin
                opt_cs_q <= 1'b1;
                if (!col_cnt[0]) begin
                    opt_sck_q <= 1'b0;
                    opt_l_q   <= in_hdr_win_q ? hdr_nibble_q : pix_shift_l[15:12];
                    opt_r_q   <= in_hdr_win_q ? hdr_nibble_q : pix_shift_r[15:12];
                end else begin
                    opt_sck_q <= 1'b1;
                end
            end else begin
                opt_cs_q  <= 1'b0;
                opt_sck_q <= 1'b0;
                opt_l_q   <= 4'h0;
                opt_r_q   <= 4'h0;
            end
        end
    end

endmodule
