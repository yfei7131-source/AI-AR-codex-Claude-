// Directed protocol-boundary regression, no vendor optical payload assumed.
// The pinned PR25 baseline is separately compiled to witness the reserved-bit
// bug. Fixed RTL then exercises real input CS/SCK/QIO and its FIFO sink.
`timescale 1ns / 1ps
module tb_evt1_host_framing;
    reg clk = 0, sck = 0, cs = 1;
    reg [3:0] qio = 0;
    wire out_sck, out_cs, d3;
    wire [3:0] left_data, right_data;
    integer writes = 0;
    integer tests = 0;
    integer n, flag, before_writes;
    reg before_raw_toggle;
    always #10.416667 clk = ~clk;
    evt1_ar_display_fpga_bridge_rev_c dut(
        .clk_48m(clk), .host_sck(sck), .host_cs_n(cs), .host_qio(qio),
        .opt_sck(out_sck), .opt_cs_n(out_cs),
        .opt_l_qdo(left_data), .opt_r_qdo(right_data), .cdone_vsync_n(d3)
    );
    initial begin
        #20000000;
        $fatal(1, "host framing regression exceeded 20 ms modeled time");
    end

    always @(posedge sck) begin
        if (dut.fifo_we_h) begin
            case (writes)
                0: if ({dut.fifo_wdata_ctrl, dut.fifo_wdata_hi, dut.fifo_wdata_lo} !== 48'h000001231234)
                    $fatal(1, "partial-tail transaction corrupted the complete first pixel");
                1: if ({dut.fifo_wdata_ctrl, dut.fifo_wdata_hi, dut.fifo_wdata_lo} !== 48'h00034affbeef)
                    $fatal(1, "CS restart corrupted command/address/word after partial pixel");
                default: $fatal(1, "unexpected FIFO write after malformed or truncated request");
            endcase
            writes = writes + 1;
        end
    end

    task nibble(input [3:0] value);
        begin
            sck = 0; qio = value; #12.5;
            sck = 1; #12.5;
            sck = 0;
        end
    endtask
    task end_cs;
        begin
            sck = 0; #1; cs = 1; #100;
            if (dut.h_nib_cnt !== 0) $fatal(1, "CS high did not reset nibble framing");
        end
    endtask
    task prefix(input [39:0] value, input integer nibble_count);
        integer index;
        begin
            #1; cs = 0;
            for (index=0; index<nibble_count; index=index+1)
                nibble(value[(9-index)*4 +: 4]);
        end
    endtask
    task control(input [3:0] flags);
        begin
            prefix({36'hA40000000, flags}, 10);
            end_cs;
        end
    endtask
    task off_unchanged;
        begin
            if (dut.opt_pwr_off_h !== 1 || dut.opt_scan_en_h !== 0 ||
                dut.raw_window_q !== 0 || dut.raw_req_tgl_h !== before_raw_toggle)
                $fatal(1, "malformed/truncated control altered OFF, scan, or RAW state");
            if (d3 !== 0 || out_sck !== 0 || out_cs !== 1 || left_data !== 0 || right_data !== 0)
                $fatal(1, "malformed/truncated request escaped the optical shutdown clamp");
        end
    endtask

`ifdef BASELINE_EXPECT_RESERVED_BUG
    initial begin
        #1000;
        control(0);
        if (dut.opt_pwr_off_h !== 1) $fatal(1, "baseline OFF fixture not established");
        // The published A4 ICD reserves bit3=0. 0xB must not grant power or scan.
        control(4'hB);
        if (dut.opt_pwr_off_h !== 0 || dut.opt_scan_en_h !== 1)
            $fatal(1, "pinned baseline did not reproduce the expected reserved-bit bug");
        $display("BASELINE_PR25_RESERVED_CTRL_BUG: PASS (witness only: invalid flag0xB granted power/scan; baseline is not safety-approved)");
        $finish;
    end
`else
    initial begin
        #1000;
        control(0);
        before_raw_toggle = dut.raw_req_tgl_h;
        // Abort at every position before the tenth/control-completion nibble.
        // This exercises asynchronous CS framing, not a physical pad pulse bound.
        for (n=0; n<10; n=n+1) begin
            prefix(40'hA400000003, n);
            end_cs;
            off_unchanged;
        end
        tests = tests + 1;
        $display("HOST_FRAMING_CASE truncated_controls_0_to_9_nibbles: PASS");

        for (flag=8; flag<16; flag=flag+1) begin
            control(flag[3:0]);
            off_unchanged;
        end
        tests = tests + 1;
        $display("HOST_FRAMING_CASE all_reserved_bit_controls_rejected: PASS");

        // First-word consumption must still occur on rejection. Additional
        // legal-looking data cannot apply a second control under the same CS.
        prefix(40'hA40000000B, 10);
        nibble(0); nibble(0); nibble(0); nibble(2);
        end_cs;
        off_unchanged;
        tests = tests + 1;
        $display("HOST_FRAMING_CASE rejected_word_cannot_retry_inside_same_CS: PASS");

        // A high-CS clock train after an aborted A4 prefix is not a transaction.
        prefix(40'hA400000003, 3);
        end_cs;
        for (n=0; n<16; n=n+1) nibble(n[3:0]);
        off_unchanged;
        if (writes != 0) $fatal(1, "high-CS clocks wrote a pixel");
        tests = tests + 1;
        $display("HOST_FRAMING_CASE high_CS_serial_noise_ignored: PASS");

        // The same legal reserved bits inside RAW must remain vendor-opaque.
        // This is synthetic data; it is not a JBD initialization sequence.
        control(2);
        if (dut.opt_pwr_off_h !== 0) $fatal(1, "valid control did not recover after rejected packets");
        wait (dut.opt_pwr_inhibit === 0);
        control(6);
        if (dut.raw_window_q !== 1) $fatal(1, "valid powered RAW arm was rejected");
        #1; cs = 0;
        for (n=0; n<10; n=n+1) begin
            case (n)
                0: qio = 4'hA;
                1: qio = 4'h4;
                9: qio = 4'hB;
                default: qio = 0;
            endcase
            sck = 0; #12.5; sck = 1; #1;
            if (out_sck !== 1 || out_cs !== 0 || left_data !== qio || right_data !== qio)
                $fatal(1, "reserved-looking RAW nibble was filtered or corrupted");
            #11.5; sck = 0;
        end
        end_cs;
        if (dut.raw_window_q !== 0 || dut.opt_scan_en_h !== 0 || dut.opt_pwr_off_h !== 0)
            $fatal(1, "opaque RAW A4/0xB incorrectly changed control state");
        tests = tests + 1;
        $display("HOST_FRAMING_CASE RAW_reserved_pattern_remains_opaque: PASS");

        control(0);
        before_raw_toggle = dut.raw_req_tgl_h;
        off_unchanged;
        tests = tests + 1;
        $display("HOST_FRAMING_CASE legitimate_OFF_after_RAW: PASS");

        before_writes = writes;
        for (n=0; n<10; n=n+1) begin
            prefix(40'hA001231234, n);
            end_cs;
            if (writes != before_writes) $fatal(1, "incomplete pixel wrote FIFO");
        end
        tests = tests + 1;
        $display("HOST_FRAMING_CASE truncated_pixel_headers_and_words: PASS");

        prefix(40'hA001231234, 10);  // complete first pixel
        nibble(4'hD); nibble(4'hE); nibble(4'hA); // incomplete second word
        end_cs;
        prefix(40'hA34AFFBEEF, 10);  // independent transaction must restart decode
        end_cs;
        if (writes != 2) $fatal(1, "complete-prefix/partial-tail recovery lost or duplicated writes");
        tests = tests + 1;
        $display("HOST_FRAMING_CASE partial_burst_tail_and_next_CS_recovery: PASS");
        if (tests != 8) $fatal(1, "missing framing regression groups");
        $display("EVT1_HOST_FRAMING_RESULT: PASS (8 directed groups; no physical pad/CDC/optical qualification claimed)");
        $finish;
    end
`endif
endmodule
