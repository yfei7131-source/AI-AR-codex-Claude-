// Rev D1.1 user-mode RTL fault tests. NOT a model of hard CDONE, CRESET_B,
// unconfigured FPGA I/O, analog AVDD or an unpowered device. Those states must
// be exercised by the separate board/supervisor model and physical tests.
`timescale 1ns / 1ps

module tb_evt1_rev_d1_1_safety;
    reg clk_48m = 0;
    reg run_clk = 1;
    reg host_sck = 0;
    reg host_cs_n = 1;
    reg [3:0] host_qio = 0;
    wire opt_sck, opt_cs_n, cdone_vsync_n;
    wire [3:0] opt_l_qdo, opt_r_qdo;
    integer cycles = 0;
    integer cases_passed = 0;
    integer c0, c1, c2, k;
    reg guard_idle = 0;

    always #10.416667 if (run_clk) clk_48m = ~clk_48m;
    always @(posedge clk_48m) cycles = cycles + 1;
    evt1_ar_display_fpga_bridge_rev_c dut(
        .clk_48m(clk_48m), .host_sck(host_sck), .host_cs_n(host_cs_n),
        .host_qio(host_qio), .opt_sck(opt_sck), .opt_cs_n(opt_cs_n),
        .opt_l_qdo(opt_l_qdo), .opt_r_qdo(opt_r_qdo),
        .cdone_vsync_n(cdone_vsync_n)
    );

    initial begin
        #200000000;
        $fatal(1, "Rev D1.1 safety test timeout (200 ms modeled time)");
    end

    always @(opt_sck or opt_cs_n or opt_l_qdo or opt_r_qdo) begin
        if (guard_idle) begin
            #0.1;
            if (opt_sck !== 0 || opt_cs_n !== 1 || opt_l_qdo !== 0 || opt_r_qdo !== 0)
                $fatal(1, "Optical bus left idle during shutdown/release");
        end
    end

    task nibble(input [3:0] n);
        begin
            host_sck = 0; host_qio = n; #12.5;
            host_sck = 1; #12.5;
        end
    endtask

    task ctrl(input [3:0] n);
        begin
            #1; host_cs_n = 0;
            nibble(4'hA); nibble(4'h4);
            nibble(0); nibble(0); nibble(0); nibble(0);
            nibble(0); nibble(0); nibble(0); nibble(n);
            host_sck = 0; #12.5; host_cs_n = 1; #100;
        end
    endtask

    task idle_check;
        begin
            if (opt_sck !== 0 || opt_cs_n !== 1 || opt_l_qdo !== 0 || opt_r_qdo !== 0)
                $fatal(1, "Expected SCK0 / CS_N1 / DATA0");
        end
    endtask

    task freeze_clock(input phase);
        begin
            if (phase) @(posedge clk_48m); else @(negedge clk_48m);
            #1; run_clk = 0; #50;
            if (clk_48m !== phase) $fatal(1, "Clock injection did not freeze requested level");
        end
    endtask

    task restart_clock;
        begin
            run_clk = 1;
            repeat (80) @(posedge clk_48m);
            #1;
        end
    endtask

`ifdef BASELINE_EXPECT_BUG
    // The unmodified PR21 design must reproduce the known failure. A successful
    // witness is not a safety PASS for the baseline; it proves the fault exists.
    initial begin
        repeat (64) @(posedge clk_48m);
        #1;
        wait (cdone_vsync_n === 1);
        freeze_clock(1'b1);
        ctrl(4'h0);
        if (dut.opt_pwr_off_h !== 1) $fatal(1, "Baseline OFF command was not decoded");
        if (cdone_vsync_n !== 1)
            $fatal(1, "Expected unmodified D1 stalled-clock OFF failure was not reproduced");
        $display("BASELINE_WITNESS clock_stopped_high: OFF decoded but D3 remained HIGH");
        ctrl(4'h2);
        if (cdone_vsync_n !== 1) $fatal(1, "Unexpected baseline behavior on stopped-clock ON");
        $display("BASELINE_D1_FAILURE_WITNESS: PASS (known unsafe D3-high state reproduced; baseline is not safety-approved)");
        $finish;
    end
`else
    task frozen_off_on(input clk_phase, input d3_phase);
        begin
            ctrl(4'h2);
            repeat (16) @(posedge clk_48m);
            wait (cdone_vsync_n === d3_phase);
            freeze_clock(clk_phase);
            if (cdone_vsync_n !== d3_phase) $fatal(1, "D3 changed before clock freeze");
            ctrl(4'h0);
            if (cdone_vsync_n !== 0 || dut.pwr_off_sync !== 2'b11)
                $fatal(1, "OFF did not asynchronously assert at stopped clk=%b D3=%b", clk_phase, d3_phase);
            idle_check;
            guard_idle = 1;
            // Re-arm before any 48 MHz edge must not bypass the shutdown latch.
            ctrl(4'h2);
            if (cdone_vsync_n !== 0 || dut.pwr_off_sync !== 2'b11)
                $fatal(1, "ON released shutdown without running clock");
            idle_check;
            restart_clock;
            if (dut.pwr_off_sync !== 0 || dut.opt_scan_en_h !== 0)
                $fatal(1, "Clock recovery did not release power in stopped-scan state");
            idle_check;
            guard_idle = 0;
            cases_passed = cases_passed + 1;
            $display("SAFETY_CASE frozen_clk_%0d_D3_%0d_OFF_ON: PASS", clk_phase, d3_phase);
        end
    endtask

    initial begin
        repeat (64) @(posedge clk_48m);
        #1; idle_check;
        if (dut.opt_scan_en_h !== 0) $fatal(1, "SCAN_EN default changed");
        // Heartbeats are independent of SCAN_EN so host can initialize optics
        // before enabling scan. This is user-mode behavior, not proof of CDONE.
        @(negedge cdone_vsync_n); c0 = cycles;
        @(posedge cdone_vsync_n); c1 = cycles;
        @(negedge cdone_vsync_n); c2 = cycles;
        if (c1-c0 != 48 || c2-c0 != 800000)
            $fatal(1, "Heartbeat changed: low=%0d period=%0d", c1-c0, c2-c0);
        idle_check;
        cases_passed = cases_passed + 1;
        $display("SAFETY_CASE scan_off_heartbeat: PASS (48 clocks LOW / 800000 clocks period)");

        frozen_off_on(0, 1);
        frozen_off_on(1, 1);
        frozen_off_on(0, 0);
        frozen_off_on(1, 0);

        // A malformed power-off control word must not leave SCAN_EN or RAW_ARM
        // active. There is no claim that truncation preserves a panel command.
        ctrl(4'h1); repeat (8) @(posedge clk_48m); #1;
        if (dut.opt_scan_en_h !== 0 || cdone_vsync_n !== 0)
            $fatal(1, "SCAN_EN accepted while OPT_PWR_REQ=0");
        ctrl(4'h4); repeat (8) @(posedge clk_48m); #1;
        if (dut.raw_window_q !== 0) $fatal(1, "RAW_ARM accepted while OPT_PWR_REQ=0");
        idle_check;
        cases_passed = cases_passed + 1;
        $display("SAFETY_CASE OFF_rejects_scan_and_RAW: PASS");

        // Stop an active serializer at SCK=1. OFF must drive safe idle despite
        // the stopped clock, and ON without a new SCAN_EN must not expose stale
        // CS/data/clock while the synchronizers recover.
        ctrl(4'h3);
        wait (opt_cs_n === 0 && opt_sck === 1);
        freeze_clock(1);
        ctrl(4'h1);
        idle_check;
        if (cdone_vsync_n !== 0) $fatal(1, "Active scan OFF did not clamp D3");
        guard_idle = 1;
        ctrl(4'h2);
        idle_check;
        restart_clock;
        idle_check;
        guard_idle = 0;
        cases_passed = cases_passed + 1;
        $display("SAFETY_CASE active_scan_abort_and_no_phantom_resume: PASS");

        // RAW remains opaque: an A4-shaped vendor payload is not a control
        // command. Check that retained feature, then inject a true internal
        // shutdown request during a second RAW transaction to test the clamp.
        ctrl(4'h2); repeat (16) @(posedge clk_48m);
        ctrl(4'h6);
        if (dut.raw_window_q !== 1) $fatal(1, "Powered RAW arm regressed");
        ctrl(4'h0); // here its A4 pattern is vendor RAW data, intentionally opaque
        if (dut.opt_pwr_off_h !== 0 || dut.raw_window_q !== 0)
            $fatal(1, "RAW A4-shaped payload was incorrectly decoded as control");
        cases_passed = cases_passed + 1;
        $display("SAFETY_CASE RAW_payload_is_not_control: PASS");

        ctrl(4'h6);
        host_cs_n = 0; host_qio = 4'hA; host_sck = 1; #3;
        if (opt_cs_n !== 0 || opt_sck !== 1) $fatal(1, "RAW mirror setup failed");
        freeze_clock(0);
        force dut.opt_pwr_off_h = 1'b1;
        #2;
        idle_check;
        if (cdone_vsync_n !== 0) $fatal(1, "RAW shutdown did not force D3 LOW");
        guard_idle = 1;
        release dut.opt_pwr_off_h;
        host_sck = 0; host_cs_n = 1; #100;
        ctrl(4'h2);
        if (dut.raw_window_q !== 0 || cdone_vsync_n !== 0)
            $fatal(1, "RAW or power inhibit escaped stopped-clock recovery");
        restart_clock;
        idle_check;
        guard_idle = 0;
        cases_passed = cases_passed + 1;
        $display("SAFETY_CASE RAW_internal_OFF_fault_abort: PASS");

        if (cases_passed != 9) $fatal(1, "Missing safety cases: %0d", cases_passed);
        $display("REV_D1_1_SAFETY_TB_RESULT: PASS (%0d user-mode RTL cases; hard CDONE/reset/power states are outside this model)", cases_passed);
        $finish;
    end
`endif
endmodule
