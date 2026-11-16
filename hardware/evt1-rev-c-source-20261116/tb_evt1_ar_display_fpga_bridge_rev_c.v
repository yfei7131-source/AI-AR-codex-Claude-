// =============================================================================
// Self-Checking Verilog-2005 Testbench: tb_evt1_ar_display_fpga_bridge_rev_c
// Comprehensively Verifies All 5 Rev C P0 Requirements:
//   1. Continuous Full-Frame Burst Write (19,200 Left + 19,200 Right = 38,400
//      16-bit words) across asynchronous 40.000 MHz host_sck -> 48.000 MHz
//      clk_48m clock domains, spanning directly across HBLANK prefetch stalls
//      (`col_cnt 1800..1881`) with ZERO dropped words (`fifo_overflow == 0`).
//   2. Distinct Left-Eye (`L_pat(a) = ((a * 0x1F35) ^ 0xA53C)`) and Right-Eye
//      (`R_pat(a) = ((a * 0x2D9B) ^ 0x5AC3)`) images across all 240 rows.
//   3. Framebuffer Boundary & Bank-Crossing (`0x0000`, `0x3FFF -> 0x4000`,
//      `0x4AFF`, and out-of-bounds clip at `0x4B00..0x4B01` -> `boundary_err_cnt == 2`).
//   4. Full-Frame Scanout Readback Verification (`240 rows x 80 words/row = 19,200`
//      words per eye) on rising edges of 24.000 MHz `opt_sck`, plus 12-nibble
//      row header verification.
//   5. Exact 60.000 Hz Frame Period (`800,000 clk_48m cycles = 16.6667 ms`) &
//      Tear-Free VBLANK Frame Update between Frame 0 and Frame 1 (`0 torn lines`).
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
    wire       frame_vsync_1v8;

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
        .frame_vsync_1v8(frame_vsync_1v8)
    );

    function [15:0] calc_left_word(input [15:0] addr, input [15:0] frame_salt);
        begin
            calc_left_word = ((addr * 16'h1F35) ^ 16'hA53C ^ frame_salt);
        end
    endfunction

    function [15:0] calc_right_word(input [15:0] addr, input [15:0] frame_salt);
        begin
            calc_right_word = ((addr * 16'h2D9B) ^ 16'h5AC3 ^ (~frame_salt));
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
            host_cs_n = 1'b0;
            qspi_send_nibble(cmd[7:4]);
            qspi_send_nibble(cmd[3:0]);
            qspi_send_nibble(start_addr[15:12]);
            qspi_send_nibble(start_addr[11:8]);
            qspi_send_nibble(start_addr[7:4]);
            qspi_send_nibble(start_addr[3:0]);

            for (w_idx = 0; w_idx < num_words; w_idx = w_idx + 1) begin
                cur_a = start_addr + w_idx[15:0];
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

    integer    r_idx, w_idx, nib_i;
    integer    mismatch_cnt;
    integer    torn_line_cnt;
    integer    vsync_c0, vsync_c1, frame_clks;
    reg [15:0] cap_l, cap_r, exp_l, exp_r;
    reg [47:0] cap_hdr_l, cap_hdr_r, exp_hdr;
    reg [15:0] addr_chk;

    integer clk_counter = 0;
    always @(posedge clk_48m) clk_counter <= clk_counter + 1;

    initial begin
        mismatch_cnt  = 0;
        torn_line_cnt = 0;

        // 1. Wait for internal POR release (16 cycles of clk_48m; starts at row_cnt=240 VBLANK)
        repeat (24) @(posedge clk_48m);

        // 2. Continuous Full-Frame Burst Write (19,200 Left words + 19,200 Right words + 2 out-of-bounds words)
        //    Note: 19,202 words = 1.92 ms per eye; spans across multiple 2000-cycle lines and HBLANK windows!
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

        // 3. Wait for Frame 0 VSYNC rising edge (row_cnt == 0, col_cnt == 0) and verify all 240 rows
        @(posedge frame_vsync_1v8);
        vsync_c0 = clk_counter;

        for (r_idx = 0; r_idx < 240; r_idx = r_idx + 1) begin
            wait (dut.opt_cs_n == 1'b0 && dut.row_cnt == r_idx[8:0]);
            cap_hdr_l = 48'd0;
            cap_hdr_r = 48'd0;
            for (nib_i = 0; nib_i < 12; nib_i = nib_i + 1) begin
                @(posedge opt_sck);
                cap_hdr_l = {cap_hdr_l[43:0], opt_l_qdo};
                cap_hdr_r = {cap_hdr_r[43:0], opt_r_qdo};
            end
            exp_hdr = {8'h32, 7'd0, r_idx[8:0], 24'h000000};
            if (cap_hdr_l !== exp_hdr || cap_hdr_r !== exp_hdr)
                mismatch_cnt = mismatch_cnt + 1;

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
                if (cap_l !== exp_l || cap_r !== exp_r || cap_l === cap_r)
                    mismatch_cnt = mismatch_cnt + 1;
            end
            wait (dut.opt_cs_n == 1'b1);
        end

        // 4. During Frame 0 VBLANK (row_cnt == 240..399), write Frame 1 with Tear-Guarded Commands (0xA2 / 0xA3)
        wait (dut.row_cnt == 9'd240);
        qspi_burst_write_frame(8'hA2, 16'h0000, 19200, 1'b0, 16'h0F0F);
        qspi_burst_write_frame(8'hA3, 16'h0000, 19200, 1'b1, 16'h0F0F);

        // 5. Measure exact 60.000 Hz cycle period on Frame 1 VSYNC and verify Tear-Free transition
        @(posedge frame_vsync_1v8);
        vsync_c1   = clk_counter;
        frame_clks = vsync_c1 - vsync_c0;
        $display("[TB] Measured Frame Period = %0d clk_48m cycles (Expected 800,000 for 60.000 Hz)", frame_clks);

        for (r_idx = 0; r_idx < 240; r_idx = r_idx + 1) begin
            wait (dut.opt_cs_n == 1'b0 && dut.row_cnt == r_idx[8:0]);
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
                if (cap_l !== exp_l || cap_r !== exp_r)
                    torn_line_cnt = torn_line_cnt + 1;
            end
            wait (dut.opt_cs_n == 1'b1);
        end

        if (mismatch_cnt != 0 || torn_line_cnt != 0 || frame_clks != 800000) begin
            $display("VERILOG_TB_RESULT: FAIL (mismatches=%0d, torn=%0d, frame_clks=%0d)",
                     mismatch_cnt, torn_line_cnt, frame_clks);
            $fatal(1, "Verification failed!");
        end else begin
            $display("VERILOG_TB_RESULT: PASS (38,400/38,400 words/frame verified, 0 drops, 0 torn pixels, 800,000 clks = 60.000 Hz)");
            $finish;
        end
    end

endmodule
