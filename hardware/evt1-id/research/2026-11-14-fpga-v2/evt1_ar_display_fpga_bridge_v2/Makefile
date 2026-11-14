# Makefile for EVT-1 Binocular AR Display Bridge FPGA
RTL_SRCS = rtl/qspi_cdc_async_fifo.v rtl/s3_qspi_slave_rx.v rtl/spram_framebuffer_ctrl.v rtl/binocular_scanline_engine.v rtl/jbd_dual_bridge_top.v
TB_SRC   = tb/tb_jbd_dual_bridge.v

.PHONY: all sim synth pnr sta verify_local

all: sim synth pnr sta

sim:
	iverilog -g2005 -Wall -Irtl -o build/tb_bridge.vvp $(RTL_SRCS) $(TB_SRC)
	vvp build/tb_bridge.vvp

synth:
	yosys -p "read_verilog -DSYNTHESIS -Irtl $(RTL_SRCS); synth_ice40 -top jbd_dual_bridge_top -json build/bridge.json" | tee evidence/yosys_synth.log

pnr:
	nextpnr-ice40 --up5k --package uwg30 --json build/bridge.json --pcf constraints/ice40up5k_uwg30.pcf --asc build/bridge.asc --freq 48 | tee evidence/nextpnr.log

sta:
	icetime -d up5k -P uwg30 -p constraints/ice40up5k_uwg30.pcf -t -m build/bridge.asc | tee evidence/icetime_sta.log

verify_local:
	python3 scripts/rtl_ast_verifier_and_sim.py
