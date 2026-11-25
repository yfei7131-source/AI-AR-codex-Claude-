`timescale 1ns / 1ps
module tb_evt1_host_wire;
    reg clk = 0;
    reg sck = 0;
    reg cs = 1;
    reg [3:0] qio = 0;
    wire out_sck, out_cs, d3;
    wire [3:0] left_data, right_data;
    integer writes = 0, i, transaction = 0;
    localparam FIXTURE_LENGTH = 59;
    reg [4:0] stream [0:FIXTURE_LENGTH-1];
    always #10.4167 clk = ~clk;

    evt1_ar_display_fpga_bridge_rev_c dut(
        .clk_48m(clk), .host_sck(sck), .host_cs_n(cs), .host_qio(qio),
        .opt_sck(out_sck), .opt_cs_n(out_cs),
        .opt_l_qdo(left_data), .opt_r_qdo(right_data), .cdone_vsync_n(d3)
    );

    always @(posedge sck) begin
        if (dut.fifo_we_h) begin
            case (writes)
                0: if ({dut.fifo_wdata_ctrl, dut.fifo_wdata_hi, dut.fifo_wdata_lo} !== 48'h000001231234)
                    $fatal(1, "left first word differs");
                1: if ({dut.fifo_wdata_ctrl, dut.fifo_wdata_hi, dut.fifo_wdata_lo} !== 48'h000001245678)
                    $fatal(1, "left address increment or word differs");
                2: if ({dut.fifo_wdata_ctrl, dut.fifo_wdata_hi, dut.fifo_wdata_lo} !== 48'h00034affbeef)
                    $fatal(1, "right eye final tear-guard word differs");
                default: $fatal(1, "unexpected framebuffer write");
            endcase
            writes = writes + 1;
        end
    end

    initial begin
        $readmemh("host_wire.hex", stream);
        #1000;
        for (i=0; i<FIXTURE_LENGTH; i=i+1) begin
            if (stream[i] == 16) begin
                cs = 1;
                #100;
                case (transaction)
                    2: if (dut.raw_window_q !== 1) $fatal(1, "encoded RAW arm was rejected");
                    3: if (dut.raw_window_q !== 0 || dut.opt_pwr_off_h !== 0)
                        $fatal(1, "RAW did not close or decoded synthetic A4 payload");
                    4: if (dut.opt_pwr_off_h !== 1 || d3 !== 0 ||
                           out_sck !== 0 || out_cs !== 1 || left_data !== 0 || right_data !== 0)
                        $fatal(1, "encoded OFF failed to inhibit the optical bus");
                endcase
                transaction = transaction + 1;
            end else begin
                if (stream[i][4] !== 0) $fatal(1, "invalid wire fixture");
                cs = 0;
                qio = stream[i][3:0];
                #12.5 sck = 1;
                #1;
                if (transaction == 3 &&
                    (out_sck !== 1 || out_cs !== 0 || left_data !== qio || right_data !== qio))
                    $fatal(1, "encoded RAW did not mirror both eyes");
                #11.5 sck = 0;
                #1;
            end
        end
        if (writes != 3 || transaction != 5) $fatal(1, "host fixture execution incomplete");
        $display("HOST_WIRE_PASS: 3 pixel words, symmetric RAW, one-shot close, encoded OFF");
        $finish;
    end
endmodule
