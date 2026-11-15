// SPDX-License-Identifier: MIT
// File:     tb/tb_jbd_dual_bridge.v
// Standard: IEEE 1364-2005 Verilog
// Purpose:  Self-checking Native Verilog Testbench with non-zero exit ($fatal(1, ...)) on any failure:
//           - Test 1: OP_SET_OPTICAL_CFG (CRC = 16'h1A65)
//           - Test 2: OP_WRITE_ROI_RLE4 160B expansion (CRC = 16'h3FFC)
//           - Test 3: Corrupted CRC injection (verifies Pre-CRC EBR stage rejection, 0 SPRAM corruption)
//           - Test 4: MODE_640x400_2BPP_PP Double-Buffer Back-Bank write (0x8000) isolation
//           - Test 5: OP_COMMIT_FRAME (0x40) + VSYNC Atomic Swap + Active Row Scanout Verification
//           - Test 6: MODE_STEREO_INDEP_2BPP (2'b11) Independent Left/Right Eye Framebuffer & Scanout
//           - Test 7: OP_READ_STATUS (0x50) Bidirectional QSPI Status Readback over s3_io[3:0]

`timescale 1ns / 1ps
`include "jbd_ar_bridge_pkg.vh"

module tb_jbd_dual_bridge;
    reg        clk_48m      = 1'b0;
    reg        rst_n        = 1'b0;
    reg        s3_cs_n      = 1'b1;
    reg        s3_sclk      = 1'b0;
    reg  [3:0] s3_io_drv    = 4'h0;
    reg        s3_io_drv_en = 1'b1;
    wire [3:0] s3_io        = s3_io_drv_en ? s3_io_drv : 4'bzzzz;

    wire       opt_sclk;
    wire       opt_cs_l_n;
    wire       opt_cs_r_n;
    wire [3:0] opt_l_io;
    wire [3:0] opt_r_io;
    wire       bridge_crc_err;
    wire       bridge_cdc_err;
    wire       vsync_out;

    reg [15:0] rx_status_word;
    integer    wait_cycles;

    always #10.416 clk_48m = ~clk_48m;

    jbd_dual_bridge_top #(
        .VBLANK_CLOCKS(17'd16)
    ) dut (
        .clk_48m_in     (clk_48m),
        .rst_n          (rst_n),
        .s3_cs_n        (s3_cs_n),
        .s3_sclk        (s3_sclk),
        .s3_io          (s3_io),
        .opt_sclk       (opt_sclk),
        .opt_cs_l_n     (opt_cs_l_n),
        .opt_cs_r_n     (opt_cs_r_n),
        .opt_l_io       (opt_l_io),
        .opt_r_io       (opt_r_io),
        .bridge_crc_err (bridge_crc_err),
        .bridge_cdc_err (bridge_cdc_err),
        .vsync_out      (vsync_out)
    );

    task qspi_40mhz_send_byte;
        input [7:0] data_byte;
        begin
            s3_io_drv_en = 1'b1;
            s3_sclk = 1'b0; s3_io_drv = data_byte[7:4]; #12.5;
            s3_sclk = 1'b1; #12.5;
            s3_sclk = 1'b0; s3_io_drv = data_byte[3:0]; #12.5;
            s3_sclk = 1'b1; #12.5;
            s3_sclk = 1'b0;
        end
    endtask

    task qspi_40mhz_read_status;
        output [15:0] status_out;
        begin
            s3_cs_n = 1'b0; #25;
            // Send OP_READ_STATUS (0x50)
            qspi_40mhz_send_byte(8'h50);
            // Release host IO driver for 2 dummy/turnaround SCLK cycles (1 byte)
            s3_io_drv_en = 1'b0;
            s3_sclk = 1'b0; #12.5; s3_sclk = 1'b1; #12.5;
            s3_sclk = 1'b0; #12.5; s3_sclk = 1'b1; #12.5;
            // Read 4 nibbles (16-bit status word) launched by FPGA on negedge s3_sclk
            s3_sclk = 1'b0; #12.5; s3_sclk = 1'b1; status_out[15:12] = s3_io; #12.5;
            s3_sclk = 1'b0; #12.5; s3_sclk = 1'b1; status_out[11:8]  = s3_io; #12.5;
            s3_sclk = 1'b0; #12.5; s3_sclk = 1'b1; status_out[7:4]   = s3_io; #12.5;
            s3_sclk = 1'b0; #12.5; s3_sclk = 1'b1; status_out[3:0]   = s3_io; #12.5;
            s3_sclk = 1'b0; #25;
            s3_cs_n = 1'b1;
            s3_io_drv_en = 1'b1;
        end
    endtask

    task wait_for_vsync_and_line40_first_pixel;
        begin
            wait_cycles = 0;
            while (vsync_out !== 1'b1 && wait_cycles < 800000) begin
                @(posedge clk_48m);
                wait_cycles = wait_cycles + 1;
            end
            if (vsync_out !== 1'b1) begin
                $display("FAIL Timeout waiting for vsync_out pulse");
                $fatal(1, "Timeout waiting for vsync_out");
            end
            // Wait until scanline engine reaches active row cur_y == 40 and enters S_TX_PIXELS (state == 4)
            wait_cycles = 0;
            while (!(dut.u_scan_engine.cur_y == 10'd40 && dut.u_scan_engine.state == 3'd4 && opt_sclk == 1'b1) &&
                   wait_cycles < 200000) begin
                @(posedge clk_48m);
                wait_cycles = wait_cycles + 1;
            end
            if (!(dut.u_scan_engine.cur_y == 10'd40 && dut.u_scan_engine.state == 3'd4)) begin
                $display("FAIL Timeout waiting for active line 40 pixel transmission");
                $fatal(1, "Timeout waiting for line 40 S_TX_PIXELS");
            end
        end
    endtask

    initial begin
        $dumpfile("evidence/tb_jbd_dual_bridge.vcd");
        $dumpvars(0, tb_jbd_dual_bridge);
        #100; rst_n = 1'b1; #200;

        // Test 1: OP_SET_OPTICAL_CFG (CRC = 16'h1A65)
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h20);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h08);
        qspi_40mhz_send_byte(8'h02);
        qspi_40mhz_send_byte(8'h1A);
        qspi_40mhz_send_byte(8'h65);
        #25; s3_cs_n = 1'b1;
        #2000;
        if (bridge_crc_err !== 1'b0 || dut.u_s3_rx.good_packet_cnt !== 16'd1) begin
            $display("FAIL Test 1: crc_err=%b good=%d", bridge_crc_err, dut.u_s3_rx.good_packet_cnt);
            $fatal(1, "FAIL Test 1");
        end

        // Test 2: OP_WRITE_ROI_RLE4 (CRC = 16'h3FFC)
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h11);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h05);
        qspi_40mhz_send_byte(8'hFF);
        qspi_40mhz_send_byte(8'd158);
        qspi_40mhz_send_byte(8'h33);
        qspi_40mhz_send_byte(8'hFA);
        qspi_40mhz_send_byte(8'hCE);
        qspi_40mhz_send_byte(8'h3F);
        qspi_40mhz_send_byte(8'hFC);
        #25; s3_cs_n = 1'b1;
        #10000;
        if (bridge_crc_err !== 1'b0 || dut.u_s3_rx.good_packet_cnt !== 16'd2 ||
            dut.u_spram_ctrl.u_spram0.mem[0] !== 16'h3333 ||
            dut.u_spram_ctrl.u_spram0.mem[79] !== 16'hFACE) begin
            $display("FAIL Test 2: crc_err=%b mem[0]=%h mem[79]=%h",
                     bridge_crc_err, dut.u_spram_ctrl.u_spram0.mem[0], dut.u_spram_ctrl.u_spram0.mem[79]);
            $fatal(1, "FAIL Test 2");
        end

        // Test 3: Bad CRC Injection -> Verify SPRAM mem[0] remains 16'h3333
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h11);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h03);
        qspi_40mhz_send_byte(8'hFF);
        qspi_40mhz_send_byte(8'd16);
        qspi_40mhz_send_byte(8'h99);
        qspi_40mhz_send_byte(8'hDE);
        qspi_40mhz_send_byte(8'hAD);
        #25; s3_cs_n = 1'b1;
        #2000;
        if (bridge_crc_err !== 1'b1 || dut.u_s3_rx.bad_packet_cnt !== 16'd1 ||
            dut.u_spram_ctrl.u_spram0.mem[0] !== 16'h3333) begin
            $display("FAIL Test 3: bad_cnt=%d mem[0]=%h", dut.u_s3_rx.bad_packet_cnt, dut.u_spram_ctrl.u_spram0.mem[0]);
            $fatal(1, "FAIL Test 3");
        end

        // Test 4: Switch to MODE_640x400_2BPP_PP (2'b01) and write 80 words (160B) to Back Buffer (Bank 2 @ 0x8000)
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h20);
        qspi_40mhz_send_byte(8'h01);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h02);
        qspi_40mhz_send_byte(8'hA4);
        qspi_40mhz_send_byte(8'hFC);
        #25; s3_cs_n = 1'b1;
        #2000;

        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h11);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h03);
        qspi_40mhz_send_byte(8'hFF);
        qspi_40mhz_send_byte(8'd160);
        qspi_40mhz_send_byte(8'hE4);
        qspi_40mhz_send_byte(8'hBF);
        qspi_40mhz_send_byte(8'h32);
        #25; s3_cs_n = 1'b1;
        #10000;
        if (dut.u_spram_ctrl.u_spram2.mem[0] !== 16'hE4E4 || dut.u_spram_ctrl.u_spram0.mem[0] !== 16'h3333) begin
            $display("FAIL Test 4 Back-Buffer isolation: bank2[0]=%h bank0[0]=%h",
                     dut.u_spram_ctrl.u_spram2.mem[0], dut.u_spram_ctrl.u_spram0.mem[0]);
            $fatal(1, "FAIL Test 4");
        end

        // Test 5: OP_COMMIT_FRAME (0x40, swap_en=1, CRC=16'hD15A) + VSYNC Atomic Bank Swap & Scanout
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h40);
        qspi_40mhz_send_byte(8'h01);
        qspi_40mhz_send_byte(8'hD1);
        qspi_40mhz_send_byte(8'h5A);
        #25; s3_cs_n = 1'b1;
        #500;
        if (dut.u_scan_engine.active_front_bank !== 1'b0) begin
            $display("FAIL Test 5 Pre-VSYNC bank must stay 0");
            $fatal(1, "FAIL Test 5 Pre-VSYNC");
        end
        wait_for_vsync_and_line40_first_pixel();
        if (dut.u_scan_engine.active_front_bank !== 1'b1 || dut.u_scan_engine.act_mode !== 2'b01 ||
            opt_l_io !== 4'hF) begin
            $display("FAIL Test 5 VSYNC swap: front_bank=%b act_mode=%b opt_l_io=%h",
                     dut.u_scan_engine.active_front_bank, dut.u_scan_engine.act_mode, opt_l_io);
            $fatal(1, "FAIL Test 5 VSYNC Swap");
        end

        // Test 6: MODE_STEREO_INDEP_2BPP (2'b11) — Independent Left & Right Eye Framebuffer & Scanout
        // Configure Mode=3 (2'b11), disparity=0, mirror=0 (CRC = 16'h2130)
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h20);
        qspi_40mhz_send_byte(8'h03);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h21);
        qspi_40mhz_send_byte(8'h30);
        #25; s3_cs_n = 1'b1;
        #2000;

        // Write Left Eye line 0 (waddr=0x0000): 160B of 0xE4 ([F,A,5,0], CRC=16'hBF32)
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h11);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h03);
        qspi_40mhz_send_byte(8'hFF);
        qspi_40mhz_send_byte(8'd160);
        qspi_40mhz_send_byte(8'hE4);
        qspi_40mhz_send_byte(8'hBF);
        qspi_40mhz_send_byte(8'h32);
        #25; s3_cs_n = 1'b1;
        #10000;

        // Write Right Eye line 0 (waddr=0x8000): 160B of 0x1B ([0,5,A,F], CRC=16'h27F3)
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h11);
        qspi_40mhz_send_byte(8'h80);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h00);
        qspi_40mhz_send_byte(8'h03);
        qspi_40mhz_send_byte(8'hFF);
        qspi_40mhz_send_byte(8'd160);
        qspi_40mhz_send_byte(8'h1B);
        qspi_40mhz_send_byte(8'h27);
        qspi_40mhz_send_byte(8'hF3);
        #25; s3_cs_n = 1'b1;
        #10000;

        // Commit Stereo Frame on VSYNC
        s3_cs_n = 1'b0; #25;
        qspi_40mhz_send_byte(8'h40);
        qspi_40mhz_send_byte(8'h01);
        qspi_40mhz_send_byte(8'hD1);
        qspi_40mhz_send_byte(8'h5A);
        #25; s3_cs_n = 1'b1;

        wait_for_vsync_and_line40_first_pixel();
        if (dut.u_scan_engine.act_mode !== 2'b11 || opt_l_io !== 4'hF || opt_r_io !== 4'h0) begin
            $display("FAIL Test 6 Stereo Indep: act_mode=%b opt_l=%h opt_r=%h",
                     dut.u_scan_engine.act_mode, opt_l_io, opt_r_io);
            $fatal(1, "FAIL Test 6 Stereo Indep");
        end

        // Test 7: Bidirectional OP_READ_STATUS (0x50) QSPI Readback
        qspi_40mhz_read_status(rx_status_word);
        if (rx_status_word !== 16'h0791) begin
            $display("FAIL Test 7 OP_READ_STATUS: got=%h expected=16'h0791", rx_status_word);
            $fatal(1, "FAIL Test 7 OP_READ_STATUS");
        end

        $display("RTL_TB_ALL_7_TESTS_PASSED: good_cnt=%d bad_cnt=%d status_readback=0x%04h cdc_err=%b",
                 dut.u_s3_rx.good_packet_cnt, dut.u_s3_rx.bad_packet_cnt, rx_status_word, bridge_cdc_err);
        $finish;
    end
endmodule
