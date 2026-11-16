# =============================================================================
# Makefile for Lattice iCE40UP5K-UWG30ITR Binocular AR Display Bridge (Rev C)
# Targets:
#   make sim   -> Run Icarus Verilog simulation (iverilog + vvp)
#   make synth -> Run Yosys synthesis for iCE40 UltraPlus (synth_ice40)
#   make pnr   -> Run nextpnr-ice40 place & route (--up5k --package uwg30)
#   make sta   -> Run icetime static timing analysis (-d up5k)
# =============================================================================

TOP      = evt1_ar_display_fpga_bridge_rev_c
RTL_SRC  = evt1_ar_display_fpga_bridge_rev_c.v
SIM_MOD  = ice40_spram_ebr_sim.v
TB_SRC   = tb_evt1_ar_display_fpga_bridge_rev_c.v
PCF      = ice40up5k_uwg30_rev_c.pcf

.PHONY: all sim synth pnr sta clean

all: sim synth pnr sta

sim:
	iverilog -g2005 -o $(TOP)_sim.vvp $(RTL_SRC) $(SIM_MOD) $(TB_SRC)
	vvp $(TOP)_sim.vvp | tee iverilog_sim.log

synth:
	yosys -l yosys_synth.log -p "synth_ice40 -top $(TOP) -json $(TOP).json" $(RTL_SRC)

pnr: synth
	nextpnr-ice40 --up5k --package uwg30 --pcf $(PCF) --json $(TOP).json --asc $(TOP).asc --freq 48 -l nextpnr_uwg30.log

sta: pnr
	icetime -d up5k -P uwg30 -p $(PCF) -t -m -r $(TOP)_sta.rpt $(TOP).asc

clean:
	rm -f *.vvp *.json *.asc *.rpt *.log
