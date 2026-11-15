# Makefile for EVT-1 Binocular AR Display Bridge FPGA V2.2
RTL_SRCS = rtl/ebr_sdp_ram.v rtl/qspi_cdc_async_fifo.v rtl/s3_qspi_slave_rx.v rtl/spram_framebuffer_ctrl.v rtl/binocular_scanline_engine.v rtl/jbd_dual_bridge_top.v
TB_SRC   = tb/tb_jbd_dual_bridge.v
FW_SRCS  = firmware_driver/jbd_fpga_bridge_drv.c

.PHONY: all sim synth pnr_sg48 pnr_uwg30 sta_sg48 selfcheck_c

all: sim synth pnr_sg48 sta_sg48

sim:
	mkdir -p build
	iverilog -g2005 -Wall -Irtl -o build/tb_bridge.vvp $(RTL_SRCS) $(TB_SRC)
	vvp build/tb_bridge.vvp

synth:
	mkdir -p build
	yosys -p "read_verilog -DSYNTHESIS -Irtl $(RTL_SRCS); synth_ice40 -top jbd_dual_bridge_top -json build/bridge.json" | tee evidence/yosys_synth.log

pnr_sg48:
	nextpnr-ice40 --up5k --package sg48 --json build/bridge.json --pcf constraints/ice40up5k_sg48.pcf --asc build/bridge_sg48.asc --freq 48 | tee evidence/nextpnr_sg48.log

pnr_uwg30:
	nextpnr-ice40 --up5k --package uwg30 --json build/bridge.json --pcf constraints/ice40up5k_uwg30.pcf --asc build/bridge_uwg30.asc --freq 48 | tee evidence/nextpnr_uwg30.log

sta_sg48:
	icetime -d up5k -P sg48 -p constraints/ice40up5k_sg48.pcf -t -m build/bridge_sg48.asc | tee evidence/icetime_sta.log

selfcheck_c:
	mkdir -p build
	gcc -O2 -Wall -Wextra -Ifirmware_driver tb/dual_clock_rtl_event_sim.c $(FW_SRCS) -o build/dual_clock_rtl_event_sim
	./build/dual_clock_rtl_event_sim | tee evidence/rtl_dual_clock_test_log.txt
