// =============================================================================
// Self-Checking Verilog-2005 Testbench: tb_evt1_ar_display_fpga_bridge_rev_c (Rev D)
// Rev D additions (all Rev C checks below are retained):
//   R1. Optical scan is disabled after POR: opt_cs_n must stay HIGH until OPT_CTRL(0xA4)
//       sets SCAN_EN (unexpected_cs_cnt == 0).
//   R2. Ball D3 `cdone_vsync_n` is active-low (frame timing measured on falling edges) and
//       OPT_PWR_REQ=0 holds it LOW continuously (pwr_hold_err_cnt == 0), then releases it.
//   R3. RAW_ARM is rejected while SCAN_EN=1 (raw_reject_err_cnt == 0).
//   R4. One-shot RAW window mirrors host_sck/cs_n/qio to BOTH eyes (raw_mirror_err_cnt == 0),
//       suppresses 0xA0 framebuffer decode inside the window (no word count change), and
//       closes after exactly one transaction (raw_leak_err_cnt == 0).
// Comprehensively Verifies All Rev C P0 Requirements (With Watchdog Timeout):
//   1. Simulation Timeout Watchdog (`SIM_TIMEOUT_CLKS = 3,500,000` cycles) to
//      prevent infinite hangs in `vvp` / CI pipelines.
//   2. Fixed Binocular Pattern Generator Collision at `row = 0, addr = 16'h0000`:
//      - Previously, `calc_left_word(0, 0) = (0 * 16'h1F35) ^ 16'hA53C ^ 0 = 16'hA53C`
//        and `calc_right_word(0, 0) = (0 * 16'h2D9B) ^ 16'h5AC3 ^ (~0) = 16'h5AC3 ^ 16'hFFFF
//        = 16'hA53C` collided at `row = 0, w_idx = 0, addr = 16'h0000` because
//        `16'h5AC3 == ~16'hA53C`, triggering `cap_l === cap_r` (`mismatches = 1`).
//      - `calc_right_word` now uses `16'h5AC2` (even LSB), guaranteeing
//        `calc_left_word[0] != calc_right_word[0]` across all 65,536 addresses and salts!
//      - Added explicit `$display` diagnostic logging of row, word address, expected,
//        and actual values on any mismatch.
//   3. Continuous Full-Frame Burst Write (19,200 Left + 19,200 Right = 38,400
//      16-bit words) across asynchronous 40.000 MHz host_sck -> 48.000 MHz
//      clk_48m clock domains, spanning directly across HBLANK prefetch stalls
//      (`col_cnt 1800..1883`) with ZERO dropped words (`fifo_overflow == 0`).
//   4. Framebuffer Boundary & Bank-Crossing (`0x0000`, `0x3FFF -> 0x4000`,
//      `0x4AFF`, and out-of-bounds clip at `0x4B00` -> `boundary_err_cnt == 2`).
//   5. Full-Frame Scanout Readback Verification (`240 rows x 80 words/row = 19,200`
//      words per eye) & Exact 60.000 Hz Frame Period (`800,000 clk_48m cycles`).
//   6. True Active-Row Line-Prefetch & Anti-Tearing Verification on `row_cnt == 10`
//      (`next_row == 11 < 240`, `start_addr = 16'h0370`, `col_cnt = 1700..1883`).
// =============================================================================

`timescale 1ns / 1ps

module tb_evt1_ar_display_fpga_bridge_rev_c;

    reg        clk_48m   = 1'b0;
    reg        host_sck  = 1'b0;
    reg        host_cs_n = 1'b1;
    reg  [3:0] host_qio  = 4'h0;

    wire       opt_sck;
    wire       opt_cs_n;
    wire [3:0] opt_l_qdo;
    wire [3:0] opt_r_qdo;
    wire       cdone_vsync_n;

    // 48.000 MHz system clock (period = 20.833333 ns)
    always #10.416667 clk_48m = ~clk_48m;

    evt1_ar_display_fpga_bridge_rev_c dut (
        .clk_48m        (clk_48m),
        .host_sck       (host_sck),
        .host_cs_n      (host_cs_n),
        .host_qio       (host_qio),
        .opt_sck        (opt_sck),
        .opt_cs_n       (opt_cs_n),
        .opt_l_qdo      (opt_l_qdo),
        .opt_r_qdo      (opt_r_qdo),
        .cdone_vsync_n  (cdone_vsync_n)
    );

    // =========================================================================
    // Watchdog Timeout Protection (Prevents infinite hangs in CI / vvp)
    // =========================================================================
    localparam integer SIM_TIMEOUT_CLKS = 4500000;
    initial begin
        repeat (SIM_TIMEOUT_CLKS) @(posedge clk_48m);
        $display("VERILOG_TB_RESULT: FAIL (WATCHDOG TIMEOUT after %0d clk_48m cycles at row_cnt=%0d, col_cnt=%0d)",
                 SIM_TIMEOUT_CLKS, dut.row_cnt, dut.col_cnt);
        $fatal(1, "Simulation watchdog timeout exceeded!");
    end

    // Track whether `prefetch_active` genuinely pulsed on `row_cnt == 10`
    reg row10_prefetch_seen = 1'b0;
    always @(posedge clk_48m) begin
        if (dut.row_cnt == 9'd10 && dut.prefetch_active == 1'b1)
            row10_prefetch_seen <= 1'b1;
    end

    function [15:0] calc_left_word(input [15:0] addr, input [15:0] frame_salt);
        begin
            calc_left_word = ((addr * 16'h1F35) ^ 16'hA53C ^ frame_salt);
        end
    endfunction

    // Uses 16'h5AC2 (bit[0]=0) with ~frame_salt so calc_right_word[0] == ~calc_left_word[0]
    // for all 65,536 addresses (fixing the row=0, addr=0x0000 0xA53C==0xA53C collision)
    function [15:0] calc_right_word(input [15:0] addr, input [15:0] frame_salt);
        begin
            calc_right_word = ((addr * 16'h2D9B) ^ 16'h5AC2 ^ (~frame_salt));
        end
    endfunction

    // 40.000 MHz Host QSPI nibble shift (12.5 ns low + 12.5 ns high = 25.0 ns/nibble = 100.0 ns/word)
    task qspi_send_nibble(input [3:0] nib);
        begin
            host_sck = 1'b0;
            host_qio = nib;
            #12.5;
            host_sck = 1'b1;
            #12.5;
        end
    endtask

    // Continuous burst write of `num_words` consecutive 16-bit words starting at `start_addr`
    task qspi_burst_write_frame(
        input [7:0]  cmd,
        input [15:0] start_addr,
        input integer num_words,
        input        is_right_eye,
        input [15:0] frame_salt
    );
        integer w_idx;
        reg [15:0] cur_a;
        reg [15:0] w_val;
        begin
            #1.0; // 1.0 ns phase offset from clk_48m wait() edges for zero delta-cycle ambiguity
            host_cs_n = 1'b0;
            qspi_send_nibble(cmd[7:4]);
            qspi_send_nibble(cmd[3:0]);
            qspi_send_nibble(start_addr[15:12]);
            qspi_send_nibble(start_addr[11:8]);
            qspi_send_nibble(start_addr[7:4]);
            qspi_send_nibble(start_addr[3:0]);

            for (w_idx = 0; w_idx < num_words; w_idx = w_idx + 1) begin
                cur_a = start_addr + w_idx;
                if (!is_right_eye)
                    w_val = calc_left_word(cur_a, frame_salt);
                else
                    w_val = calc_right_word(cur_a, frame_salt);

                qspi_send_nibble(w_val[15:12]);
                qspi_send_nibble(w_val[11:8]);
                qspi_send_nibble(w_val[7:4]);
                qspi_send_nibble(w_val[3:0]);
            end

            host_sck  = 1'b0;
            #12.5;
            host_cs_n = 1'b1;
            #100.0;
        end
    endtask

    // Rev D: single-word OPT_CTRL write (cmd 0xA4, addr 0x0000, data 0x000{ctrl})
    task qspi_ctrl_write(input [3:0] ctrl);
        begin
            #1.0;
            host_cs_n = 1'b0;
            qspi_send_nibble(4'hA);
            qspi_send_nibble(4'h4);
            qspi_send_nibble(4'h0);
            qspi_send_nibble(4'h0);
            qspi_send_nibble(4'h0);
            qspi_send_nibble(4'h0);
            qspi_send_nibble(4'h0);
            qspi_send_nibble(4'h0);
            qspi_send_nibble(4'h0);
            qspi_send_nibble(ctrl);
            host_sck  = 1'b0;
            #12.5;
            host_cs_n = 1'b1;
            #100.0;
        end
    endtask

    // Rev D: tracked monitors
    reg     tb_scan_en          = 1'b0;
    reg     tb_raw_expect       = 1'b0;
    integer unexpected_cs_cnt   = 0;
    integer pwr_hold_err_cnt    = 0;
    integer raw_mirror_err_cnt  = 0;
    integer raw_leak_err_cnt    = 0;
    integer raw_reject_err_cnt  = 0;
    integer wr_l_before_raw, wr_r_before_raw, bnd_before_raw;

    always @(negedge opt_cs_n) begin
        if (!tb_scan_en && !tb_raw_expect)
            unexpected_cs_cnt = unexpected_cs_cnt + 1;
    end

    // RAW transaction: 10 nibbles starting with 0xA0 (must NOT be decoded as a framebuffer write)
    task qspi_raw_mirror_check;
        reg [39:0] pat;
        integer k;
        begin
            pat = 40'hA0_0000_1234;
            #1.0;
            host_cs_n = 1'b0;
            #1.0;
            if (opt_cs_n !== 1'b0) raw_mirror_err_cnt = raw_mirror_err_cnt + 1;
            for (k = 9; k >= 0; k = k - 1) begin
                host_sck = 1'b0;
                host_qio = pat[k*4 +: 4];
                #6.0;
                if (opt_sck !== 1'b0 || opt_l_qdo !== host_qio || opt_r_qdo !== host_qio)
                    raw_mirror_err_cnt = raw_mirror_err_cnt + 1;
                #6.5;
                host_sck = 1'b1;
                #1.0;
                if (opt_sck !== 1'b1 || opt_cs_n !== 1'b0 || opt_l_qdo !== host_qio || opt_r_qdo !== host_qio)
                    raw_mirror_err_cnt = raw_mirror_err_cnt + 1;
                #11.5;
            end
            host_sck  = 1'b0;
            #12.5;
            host_cs_n = 1'b1;
            #1.0;
            if (opt_cs_n !== 1'b1) raw_mirror_err_cnt = raw_mirror_err_cnt + 1;
            #100.0;
        end
    endtask

    integer    r_idx, w_idx, nib_i;
    integer    mismatch_cnt;
    integer    torn_line_cnt;
    integer    active_tear_err_cnt;
    integer    vsync_c0, vsync_c1, frame_clks;
    reg [15:0] cap_l, cap_r, exp_l, exp_r;
    reg [47:0] cap_hdr_l, cap_hdr_r, exp_hdr;
    reg [15:0] addr_chk;
    reg [8:0]  target_row;

    integer clk_counter = 0;
    always @(posedge clk_48m) clk_counter <= clk_counter + 1;

    initial begin
        mismatch_cnt        = 0;
        torn_line_cnt       = 0;
        active_tear_err_cnt = 0;

        // 1. Wait for internal POR release (16 cycles of clk_48m; starts at row_cnt=240 VBLANK)
        repeat (24) @(posedge clk_48m);

        // 2. Continuous Full-Frame Burst Write (19,200 Left words + 19,200 Right words + 2 out-of-bounds words)
        $display("[TB] Starting Continuous Full-Frame Burst #1 (19,200 L + 19,200 R + 2 boundary words)...");
        qspi_burst_write_frame(8'hA0, 16'h0000, 19201, 1'b0, 16'h0000); // Includes 0x4B00 OOB test #1
        qspi_burst_write_frame(8'hA1, 16'h0000, 19201, 1'b1, 16'h0000); // Includes 0x4B00 OOB test #2

        // Wait 80 clk_48m cycles for final FIFO drain
        repeat (80) @(posedge clk_48m);

        $display("[TB] Burst #1 Complete: words_written_l=%0d, words_written_r=%0d, fifo_max_level=%0d, overflow=%0b, boundary_err_cnt=%0d",
                 dut.words_written_l, dut.words_written_r, dut.fifo_max_level, dut.fifo_overflow_sticky, dut.boundary_err_cnt);

        if (dut.words_written_l !== 32'd19200 || dut.words_written_r !== 32'd19200 ||
            dut.fifo_overflow_sticky !== 1'b0 || dut.boundary_err_cnt !== 16'd2) begin
            $display("VERILOG_TB_RESULT: FAIL (CDC count or boundary clip mismatch)");
            $fatal(1, "CDC full-frame write count or boundary error count mismatch!");
        end

        // Rev D R1: scan was disabled during Burst #1 -> no optical CS activity allowed so far.
        //            Enable scanning (SCAN_EN=1, OPT_PWR_REQ=1) before the Frame 0 check.
        tb_scan_en = 1'b1;
        qspi_ctrl_write(4'b0011);

        // 3. Wait for Frame 0 VSYNC (Rev D: falling edge of active-low cdone_vsync_n) and verify all 240 rows
        @(negedge cdone_vsync_n);
        vsync_c0 = clk_counter;

        for (r_idx = 0; r_idx < 240; r_idx = r_idx + 1) begin
            target_row = r_idx;
            wait (dut.opt_cs_n == 1'b0 && dut.row_cnt == target_row);
            cap_hdr_l = 48'd0;
            cap_hdr_r = 48'd0;
            for (nib_i = 0; nib_i < 12; nib_i = nib_i + 1) begin
                @(posedge opt_sck);
                cap_hdr_l = {cap_hdr_l[43:0], opt_l_qdo};
                cap_hdr_r = {cap_hdr_r[43:0], opt_r_qdo};
            end
            exp_hdr = {8'h32, 7'd0, target_row, 24'h000000};
            if (cap_hdr_l !== exp_hdr || cap_hdr_r !== exp_hdr) begin
                $display("[TB][HDR_MISMATCH] row=%0d exp_hdr=0x%012h cap_hdr_l=0x%012h cap_hdr_r=0x%012h",
                         r_idx, exp_hdr, cap_hdr_l, cap_hdr_r);
                mismatch_cnt = mismatch_cnt + 1;
            end

            for (w_idx = 0; w_idx < 80; w_idx = w_idx + 1) begin
                cap_l = 16'h0000;
                cap_r = 16'h0000;
                for (nib_i = 0; nib_i < 4; nib_i = nib_i + 1) begin
                    @(posedge opt_sck);
                    cap_l = {cap_l[11:0], opt_l_qdo};
                    cap_r = {cap_r[11:0], opt_r_qdo};
                end
                addr_chk = r_idx * 80 + w_idx;
                exp_l    = calc_left_word(addr_chk, 16'h0000);
                exp_r    = calc_right_word(addr_chk, 16'h0000);
                if (cap_l !== exp_l || cap_r !== exp_r || cap_l === cap_r) begin
                    $display("[TB][DATA_MISMATCH] row=%0d w_idx=%0d addr=0x%04h exp_l=0x%04h actual_l=0x%04h exp_r=0x%04h actual_r=0x%04h",
                             r_idx, w_idx, addr_chk, exp_l, cap_l, exp_r, cap_r);
                    mismatch_cnt = mismatch_cnt + 1;
                end
            end
            wait (dut.opt_cs_n == 1'b1);
        end

        // 4. During Frame 0 VBLANK (row_cnt == 240..399), write Frame 1 with Tear-Guarded Commands (0xA2 / 0xA3)
        wait (dut.row_cnt == 9'd240);
        qspi_burst_write_frame(8'hA2, 16'h0000, 19200, 1'b0, 16'h0F0F);
        qspi_burst_write_frame(8'hA3, 16'h0000, 19200, 1'b1, 16'h0F0F);

        // 5. Measure exact 60.000 Hz cycle period on Frame 1 VSYNC and verify Tear-Free transition
        @(negedge cdone_vsync_n);
        vsync_c1   = clk_counter;
        frame_clks = vsync_c1 - vsync_c0;
        $display("[TB] Measured Frame Period = %0d clk_48m cycles (Expected 800,000 for 60.000 Hz)", frame_clks);

        for (r_idx = 0; r_idx < 240; r_idx = r_idx + 1) begin
            target_row = r_idx;
            wait (dut.opt_cs_n == 1'b0 && dut.row_cnt == target_row);
            for (nib_i = 0; nib_i < 12; nib_i = nib_i + 1)
                @(posedge opt_sck);
            for (w_idx = 0; w_idx < 80; w_idx = w_idx + 1) begin
                cap_l = 16'h0000;
                cap_r = 16'h0000;
                for (nib_i = 0; nib_i < 4; nib_i = nib_i + 1) begin
                    @(posedge opt_sck);
                    cap_l = {cap_l[11:0], opt_l_qdo};
                    cap_r = {cap_r[11:0], opt_r_qdo};
                end
                addr_chk = r_idx * 80 + w_idx;
                exp_l    = calc_left_word(addr_chk, 16'h0F0F);
                exp_r    = calc_right_word(addr_chk, 16'h0F0F);
                if (cap_l !== exp_l || cap_r !== exp_r) begin
                    $display("[TB][TORN_MISMATCH] row=%0d w_idx=%0d addr=0x%04h exp_l=0x%04h actual_l=0x%04h exp_r=0x%04h actual_r=0x%04h",
                             r_idx, w_idx, addr_chk, exp_l, cap_l, exp_r, cap_r);
                    torn_line_cnt = torn_line_cnt + 1;
                end
            end
            wait (dut.opt_cs_n == 1'b1);
        end

        // 6. True Active-Row Line-Prefetch & Anti-Tearing Collision Test on `row_cnt == 10` (`next_row == 11`):
        row10_prefetch_seen = 1'b0;
        wait (dut.row_cnt == 9'd10 && dut.col_cnt == 11'd1700);
        fork
            begin
                qspi_burst_write_frame(8'hA2, 16'h0370, 80, 1'b0, 16'h55AA);
            end
            begin
                wait (dut.opt_cs_n == 1'b0 && dut.row_cnt == 9'd11);
                for (nib_i = 0; nib_i < 12; nib_i = nib_i + 1)
                    @(posedge opt_sck);
                for (w_idx = 0; w_idx < 80; w_idx = w_idx + 1) begin
                    cap_l = 16'h0000;
                    for (nib_i = 0; nib_i < 4; nib_i = nib_i + 1) begin
                        @(posedge opt_sck);
                        cap_l = {cap_l[11:0], opt_l_qdo};
                    end
                    addr_chk = 16'h0370 + w_idx;
                    exp_l    = calc_left_word(addr_chk, 16'h0F0F); // Must still be intact 0x0F0F frame!
                    if (cap_l !== exp_l) begin
                        $display("[TB][ACTIVE_TEAR_ERR] row=11 w_idx=%0d addr=0x%04h exp_l=0x%04h actual_l=0x%04h",
                                 w_idx, addr_chk, exp_l, cap_l);
                        active_tear_err_cnt = active_tear_err_cnt + 1;
                    end
                end
            end
        join

        repeat (120) @(posedge clk_48m);

        // ===================== Rev D R2: OPT_PWR_REQ=0 holds D3 LOW =====================
        qspi_ctrl_write(4'b0001);                 // SCAN_EN=1, OPT_PWR_REQ=0
        repeat (8) @(posedge clk_48m);
        repeat (50000) begin
            @(posedge clk_48m);
            if (cdone_vsync_n !== 1'b0) pwr_hold_err_cnt = pwr_hold_err_cnt + 1;
        end
        qspi_ctrl_write(4'b0011);                 // power request restored
        repeat (200) @(posedge clk_48m);
        if (!(dut.row_cnt == 9'd0 && dut.col_cnt < 11'd60) && cdone_vsync_n !== 1'b1)
            pwr_hold_err_cnt = pwr_hold_err_cnt + 1;

        // ===================== Rev D R3: RAW_ARM rejected while SCAN_EN=1 ===============
        qspi_ctrl_write(4'b0111);                 // RAW_ARM with SCAN_EN=1 -> must be ignored
        repeat (8) @(posedge clk_48m);
        if (dut.raw_window_q !== 1'b0) raw_reject_err_cnt = raw_reject_err_cnt + 1;

        // ===================== Rev D R4: one-shot RAW pass-through ======================
        qspi_ctrl_write(4'b0010);                 // SCAN_EN=0, OPT_PWR_REQ=1
        repeat (2000) @(posedge clk_48m);         // scan engine idles (line truncated by design)
        tb_scan_en = 1'b0;
        qspi_ctrl_write(4'b0110);                 // RAW_ARM accepted (SCAN_EN already 0)
        if (dut.raw_window_q !== 1'b1) raw_mirror_err_cnt = raw_mirror_err_cnt + 1;
        wr_l_before_raw = dut.words_written_l;
        wr_r_before_raw = dut.words_written_r;
        bnd_before_raw  = dut.boundary_err_cnt;
        tb_raw_expect = 1'b1;
        qspi_raw_mirror_check;
        tb_raw_expect = 1'b0;
        repeat (40) @(posedge clk_48m);
        if (dut.words_written_l != wr_l_before_raw || dut.words_written_r != wr_r_before_raw ||
            dut.boundary_err_cnt != bnd_before_raw || dut.raw_window_q !== 1'b0)
            raw_leak_err_cnt = raw_leak_err_cnt + 1;
        qspi_ctrl_write(4'b0010);                 // normal transaction: must NOT reach the optics
        repeat (40) @(posedge clk_48m);
        $display("[TB] Rev D: unexpected_cs=%0d pwr_hold_err=%0d raw_reject_err=%0d raw_mirror_err=%0d raw_leak_err=%0d",
                 unexpected_cs_cnt, pwr_hold_err_cnt, raw_reject_err_cnt, raw_mirror_err_cnt, raw_leak_err_cnt);

        $display("[TB] Active Row 10->11 Tear-Guard Verification: row10_prefetch_seen=%0b, tear_hazard_cnt=%0d, active_tear_err_cnt=%0d, words_written_l=%0d, fifo_max_level=%0d/256, overflow=%0b",
                 row10_prefetch_seen, dut.tear_hazard_cnt, active_tear_err_cnt, dut.words_written_l, dut.fifo_max_level, dut.fifo_overflow_sticky);

        if (mismatch_cnt != 0 || torn_line_cnt != 0 || active_tear_err_cnt != 0 ||
            !row10_prefetch_seen || dut.tear_hazard_cnt == 0 ||
            dut.words_written_l !== 32'd38480 || frame_clks != 800000 || dut.fifo_overflow_sticky !== 1'b0 ||
            unexpected_cs_cnt != 0 || pwr_hold_err_cnt != 0 || raw_reject_err_cnt != 0 ||
            raw_mirror_err_cnt != 0 || raw_leak_err_cnt != 0) begin
            $display("VERILOG_TB_RESULT: FAIL (mismatches=%0d, torn=%0d, active_tear_err=%0d, prefetch_seen=%0b, tear_haz=%0d, wr_l=%0d, frame_clks=%0d, overflow=%0b)",
                     mismatch_cnt, torn_line_cnt, active_tear_err_cnt, row10_prefetch_seen, dut.tear_hazard_cnt, dut.words_written_l, frame_clks, dut.fifo_overflow_sticky);
            $fatal(1, "Verification failed!");
        end else begin
            $display("VERILOG_TB_RESULT: PASS (38,400/38,400 words/frame + Row 10->11 active prefetch tear-guard verified, 0 drops, 0 overflow, 0 torn pixels, 800,000 clks = 60.000 Hz; Rev D scan-gate/D3-power/RAW-window checks clean)");
            $finish;
        end
    end

endmodule
