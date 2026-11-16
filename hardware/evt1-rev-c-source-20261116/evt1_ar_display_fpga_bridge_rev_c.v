// =============================================================================
// Zhiyuan Yuedong (智元跃动) AI/AR Smart Glasses V1.0 — EVT-1 Rev C (P0 Fixed)
// Module: evt1_ar_display_fpga_bridge_rev_c
// Target: Lattice iCE40UP5K-UWG30ITR (30-Ball WLCSP, 2.11 x 2.54 x 0.45 mm)
//
// P0 Fixes Implemented:
//   1. Exact 18-Pin Standard CMOS PIO Mapping for UWG30 (FPGA-EB-02007 p.23):
//      - Avoids all 8 Power/GND balls (C2, B2, A3, D2, C4, D4, B4, E2),
//        dedicated CRESET_B (F3), and 3 Open-Drain RGB balls (C5, B5, A5).
//      - Shares lockstep opt_sck (E3) and opt_cs_n (C3) between Left & Right
//        engines while driving independent 4-bit Left (opt_l_qdo[3:0] on A1,A2,A4,E4)
//        and Right (opt_r_qdo[3:0] on E5,D5,F5,F4) buses -> exactly 18 CMOS PIOs!
//   2. 64-Deep Dual-Clock Gray-Code Asynchronous CDC FIFO (Zero Word Drops):
//      - Replaces the 1-deep toggle buffer that dropped words during the 82-cycle
//        HBLANK SPRAM prefetch window (`col_cnt 1800..1881`).
//      - Absorbs continuous 40MHz Host QSPI bursts (up to 18 words arriving during
//        the 1.708us HBLANK prefetch stall, with 64-word depth = 3.55x margin)
//        and drains at 1 word per clk_48m cycle (48 Mwords/s) as soon as prefetch
//        completes -> ZERO dropped words across continuous 38,400-word full frames!
//   3. Framebuffer Boundary Clip & Tear-Free Scanout Protection:
//      - Enforces hardware upper bound `MAX_FB_WORDS = 19,200` (`0x0000..0x4AFF`
//        across Bank 0 `0x0000..0x3FFF` and Bank 1 `0x4000..0x4AFF`); clips any
//        out-of-bounds address `>= 0x4B00` and increments `boundary_err_cnt`.
//      - Initializes `row_cnt` to `V_ACTIVE` (240, start of 6.667ms VBLANK) on reset
//        so Row 0 (`0x0000..0x004F`) is always prefetched at `row_cnt == 399` before
//        Frame 0 active scanout begins, and supports tear-guarded writes (`0xA2/0xA3`).
//   4. True 60.000 Hz Frame Timing & 24.000 MHz QSPI Clock from 48.000 MHz clk_48m:
//      - CLKS_PER_LINE = 2000 cycles (41.6667 us/line @ 48 MHz)
//      - TOTAL_LINES   = 400 lines (240 active lines + 160 VBLANK lines)
//      - CLKS_PER_FRAME= 2000 * 400 = 800,000 cycles = 16.6667 ms = 60.000 Hz exact!
// =============================================================================

`timescale 1ns / 1ps

module evt1_ar_display_fpga_bridge_rev_c #(
    parameter integer H_ACTIVE        = 320,
    parameter integer V_ACTIVE        = 240,
    parameter integer VBLANK_LINES    = 160,
    parameter integer BPP             = 4,
    parameter integer CMD_HDR_NIBBLES = 12,
    parameter integer CLKS_PER_LINE   = 2000,
    parameter integer FIFO_ADDR_BITS  = 6
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
    localparam integer PREFETCH_START_CLK     = 1800; // Prefetch next row from SPRAM into EBR during [1800..1881]
    localparam integer TOTAL_LINES            = V_ACTIVE + VBLANK_LINES; // 400 lines (800,000 clks = 60.000 Hz)
    localparam integer FIFO_DEPTH             = (1 << FIFO_ADDR_BITS); // 64 words deep

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
    // 64-Word x 34-Bit Dual-Clock Gray-Code Asynchronous CDC FIFO
    // Entry format: {tear_sync_mode[0], eye_sel[0], word_addr[15:0], data[15:0]}
    //   Commands supported:
    //     0xA0 : Immediate Write Left Eye SPRAM  (eye_sel=0, tear_sync=0)
    //     0xA1 : Immediate Write Right Eye SPRAM (eye_sel=1, tear_sync=0)
    //     0xA2 : Tear-Guarded Write Left Eye     (eye_sel=0, tear_sync=1)
    //     0xA3 : Tear-Guarded Write Right Eye    (eye_sel=1, tear_sync=1)
    // =========================================================================
    reg [33:0]                cdc_fifo_mem [0:FIFO_DEPTH-1];
    reg [FIFO_ADDR_BITS:0]    wptr_bin        = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0]    wptr_gray       = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0]    rptr_gray_h1    = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0]    rptr_gray_h2    = {(FIFO_ADDR_BITS+1){1'b0}};

    reg [FIFO_ADDR_BITS:0]    rptr_bin        = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0]    rptr_gray       = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0]    wptr_gray_s1    = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [FIFO_ADDR_BITS:0]    wptr_gray_s2    = {(FIFO_ADDR_BITS+1){1'b0}};

    // Verification & Diagnostics Telemetry Registers
    reg                       fifo_overflow_sticky = 1'b0;
    reg [15:0]                boundary_err_cnt     = 16'd0;
    reg [31:0]                words_written_l      = 32'd0;
    reg [31:0]                words_written_r      = 32'd0;
    reg [FIFO_ADDR_BITS:0]    fifo_max_level       = {(FIFO_ADDR_BITS+1){1'b0}};
    reg [31:0]                tear_guard_holdoffs  = 32'd0;

    wire [FIFO_ADDR_BITS:0] wptr_bin_next  = wptr_bin + 1'b1;
    wire [FIFO_ADDR_BITS:0] wptr_gray_next = (wptr_bin_next >> 1) ^ wptr_bin_next;
    wire                    fifo_full_h    = (wptr_gray == {~rptr_gray_h2[FIFO_ADDR_BITS:FIFO_ADDR_BITS-1],
                                                             rptr_gray_h2[FIFO_ADDR_BITS-2:0]});

    // Synchronize read Gray pointer into host_sck domain for full detection
    always @(posedge host_sck or negedge rst_n) begin
        if (!rst_n) begin
            rptr_gray_h1 <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_gray_h2 <= {(FIFO_ADDR_BITS+1){1'b0}};
        end else begin
            rptr_gray_h1 <= rptr_gray;
            rptr_gray_h2 <= rptr_gray_h1;
        end
    end

    // Host QSPI Slave Deserializer (host_sck domain, packet framed by host_cs_n)
    reg [3:0]  h_nib_cnt    = 4'd0;
    reg [7:0]  h_cmd_reg    = 8'h00;
    reg [15:0] h_addr_reg   = 16'h0000;
    reg [15:0] h_data_shift = 16'h0000;

    wire is_write_cmd = (h_cmd_reg == 8'hA0) || (h_cmd_reg == 8'hA1) ||
                        (h_cmd_reg == 8'hA2) || (h_cmd_reg == 8'hA3);

    always @(posedge host_sck or posedge host_cs_n) begin
        if (host_cs_n) begin
            h_nib_cnt <= 4'd0;
        end else begin
            if (h_nib_cnt == 4'd0) begin
                h_cmd_reg[7:4] <= host_qio;
                h_nib_cnt      <= 4'd1;
            end else if (h_nib_cnt == 4'd1) begin
                h_cmd_reg[3:0] <= host_qio;
                h_nib_cnt      <= 4'd2;
            end else if (h_nib_cnt == 4'd2) begin
                h_addr_reg[15:12] <= host_qio;
                h_nib_cnt         <= 4'd3;
            end else if (h_nib_cnt == 4'd3) begin
                h_addr_reg[11:8]  <= host_qio;
                h_nib_cnt         <= 4'd4;
            end else if (h_nib_cnt == 4'd4) begin
                h_addr_reg[7:4]   <= host_qio;
                h_nib_cnt         <= 4'd5;
            end else if (h_nib_cnt == 4'd5) begin
                h_addr_reg[3:0]   <= host_qio;
                h_nib_cnt         <= 4'd6;
            end else if (h_nib_cnt == 4'd6) begin
                h_data_shift[15:12] <= host_qio;
                h_nib_cnt           <= 4'd7;
            end else if (h_nib_cnt == 4'd7) begin
                h_data_shift[11:8]  <= host_qio;
                h_nib_cnt           <= 4'd8;
            end else if (h_nib_cnt == 4'd8) begin
                h_data_shift[7:4]   <= host_qio;
                h_nib_cnt           <= 4'd9;
            end else begin
                // Nibble 9 completes a 16-bit pixel word in burst mode
                if (is_write_cmd) begin
                    if (h_addr_reg < MAX_FB_WORDS) begin
                        if (!fifo_full_h) begin
                            cdc_fifo_mem[wptr_bin[FIFO_ADDR_BITS-1:0]] <= {
                                h_cmd_reg[1],
                                h_cmd_reg[0],
                                h_addr_reg,
                                {h_data_shift[15:4], host_qio}
                            };
                            wptr_bin  <= wptr_bin_next;
                            wptr_gray <= wptr_gray_next;
                        end else begin
                            fifo_overflow_sticky <= 1'b1;
                        end
                    end else begin
                        // Out-of-bounds address (>= 0x4B00) clipped safely
                        boundary_err_cnt <= boundary_err_cnt + 16'd1;
                    end
                    h_addr_reg <= h_addr_reg + 16'd1;
                end
                h_nib_cnt <= 4'd6; // Continue 4-nibble burst for consecutive words
            end
        end
    end

    // =========================================================================
    // Scanout Timing Counters (2000 clks/line x 400 lines = 800,000 clks = 60.000 Hz)
    // Initializes row_cnt to V_ACTIVE (240, start of VBLANK) on reset so Row 0
    // is prefetched at row_cnt==399 before Frame 0 Row 0 scanout starts.
    // =========================================================================
    reg [10:0] col_cnt = 11'd0;
    reg [8:0]  row_cnt = V_ACTIVE[8:0];

    wire in_active_rows  = (row_cnt < V_ACTIVE);
    wire in_qspi_burst   = in_active_rows && (col_cnt < ACTIVE_SCAN_CLKS);
    wire in_prefetch_win = (col_cnt >= PREFETCH_START_CLK) &&
                           (col_cnt < (PREFETCH_START_CLK + WORDS_PER_LINE + 2));
    wire [8:0] next_row  = (row_cnt == TOTAL_LINES - 1) ? 9'd0 : (row_cnt + 9'd1);
    wire prefetch_active = in_prefetch_win && (next_row < V_ACTIVE);

    // =========================================================================
    // Read-Side CDC FIFO Synchronizer & Tear-Guarded SPRAM Arbiter (clk_48m)
    // =========================================================================
    wire                    fifo_empty_c  = (rptr_gray == wptr_gray_s2);
    wire [FIFO_ADDR_BITS:0] rptr_bin_next = rptr_bin + 1'b1;
    wire [FIFO_ADDR_BITS:0] rptr_gray_next= (rptr_bin_next >> 1) ^ rptr_bin_next;

    // Decode synchronized wptr_gray_s2 to binary solely for FIFO level telemetry
    integer g_i;
    reg [FIFO_ADDR_BITS:0] wptr_bin_sync;
    always @(*) begin
        wptr_bin_sync[FIFO_ADDR_BITS] = wptr_gray_s2[FIFO_ADDR_BITS];
        for (g_i = FIFO_ADDR_BITS - 1; g_i >= 0; g_i = g_i - 1)
            wptr_bin_sync[g_i] = wptr_bin_sync[g_i + 1] ^ wptr_gray_s2[g_i];
    end
    wire [FIFO_ADDR_BITS:0] fifo_level_c = wptr_bin_sync - rptr_bin;

    wire [33:0] fifo_head      = cdc_fifo_mem[rptr_bin[FIFO_ADDR_BITS-1:0]];
    wire        wr_tear_sync_q = fifo_head[33];
    wire        wr_eye_q       = fifo_head[32];
    wire [15:0] wr_addr_q      = fifo_head[31:16];
    wire [15:0] wr_data_q      = fifo_head[15:0];

    // Active scanline collision check for tear-guarded mode (commands 0xA2 / 0xA3)
    wire [15:0] cur_row_base_addr  = row_cnt * WORDS_PER_LINE;
    wire [15:0] next_row_base_addr = next_row * WORDS_PER_LINE;
    wire        tear_row_collision = wr_tear_sync_q && in_active_rows &&
                                     ((wr_addr_q >= cur_row_base_addr && wr_addr_q < (cur_row_base_addr + WORDS_PER_LINE)) ||
                                      (wr_addr_q >= next_row_base_addr && wr_addr_q < (next_row_base_addr + WORDS_PER_LINE)));

    // SPRAM Write Enable: drains 1 word per clk_48m cycle whenever not prefetching
    wire spram_do_write = (!fifo_empty_c) && (!prefetch_active) && (!tear_row_collision);

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
    // Prefetches 80 x 16-bit words (320 pixels x 4bpp) per eye during HBLANK
    // =========================================================================
    reg        prefetch_valid_d1 = 1'b0;
    reg [6:0]  prefetch_idx_d1   = 7'd0;

    wire [9:0]  nibble_idx_in_line = (col_cnt >> 1) - CMD_HDR_NIBBLES;
    wire [6:0]  ebr_raddr = (col_cnt < (CMD_HDR_NIBBLES * 2 - 2)) ? 7'd0 : ((nibble_idx_in_line + 10'd1) >> 2);
    wire [15:0] ebr_rdata_l;
    wire [15:0] ebr_rdata_r;

    SB_RAM40_4K #(
        .WRITE_MODE(0),
        .READ_MODE (0)
    ) u_ebr_l (
        .RDATA (ebr_rdata_l),
        .RADDR ({4'd0, ebr_raddr}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({4'd0, prefetch_idx_d1}),
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
        .RADDR ({4'd0, ebr_raddr}),
        .RCLK  (clk_48m),
        .RCLKE (1'b1),
        .RE    (1'b1),
        .WADDR ({4'd0, prefetch_idx_d1}),
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
            wptr_gray_s1        <= {(FIFO_ADDR_BITS+1){1'b0}};
            wptr_gray_s2        <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_bin            <= {(FIFO_ADDR_BITS+1){1'b0}};
            rptr_gray           <= {(FIFO_ADDR_BITS+1){1'b0}};
            words_written_l     <= 32'd0;
            words_written_r     <= 32'd0;
            fifo_max_level      <= {(FIFO_ADDR_BITS+1){1'b0}};
            tear_guard_holdoffs <= 32'd0;
            col_cnt             <= 11'd0;
            row_cnt             <= V_ACTIVE[8:0]; // Start at VBLANK Line 240 so Row 0 prefetches at Line 399
            spram_rd_bank_d1    <= 1'b0;
            prefetch_valid_d1   <= 1'b0;
            prefetch_idx_d1     <= 7'd0;
            opt_sck             <= 1'b0;
            opt_cs_n            <= 1'b1;
            opt_l_qdo           <= 4'h0;
            opt_r_qdo           <= 4'h0;
            frame_vsync_1v8     <= 1'b0;
        end else begin
            // 1. 2-FF Gray-code write pointer synchronization into clk_48m domain
            wptr_gray_s1 <= wptr_gray;
            wptr_gray_s2 <= wptr_gray_s1;

            if (fifo_level_c > fifo_max_level)
                fifo_max_level <= fifo_level_c;

            // 2. Drain Async CDC FIFO into SPRAM when not prefetching
            if (spram_do_write) begin
                rptr_bin  <= rptr_bin_next;
                rptr_gray <= rptr_gray_next;
                if (!wr_eye_q)
                    words_written_l <= words_written_l + 32'd1;
                else
                    words_written_r <= words_written_r + 32'd1;
            end else if (!fifo_empty_c && tear_row_collision) begin
                tear_guard_holdoffs <= tear_guard_holdoffs + 32'd1;
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
