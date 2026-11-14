// SPDX-License-Identifier: MIT
// File:    firmware_driver/jbd_fpga_bridge_drv.h
// Purpose: ESP32-S3 QSPI Host Driver for EVT-1 Binocular AR FPGA Display Bridge
//          Matches hardware/evt0-r6-h02h03/evt0_core/pinmap_fw_crosscheck.csv

#ifndef JBD_FPGA_BRIDGE_DRV_H
#define JBD_FPGA_BRIDGE_DRV_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

// Exact GPIO assignments from pinmap_fw_crosscheck.csv (Zero conflict with Camera/Mic/USB)
#define GL_PIN_DISP_RST     14
#define GL_PIN_DISP_CS      21
#define GL_PIN_DISP_D0      38
#define GL_PIN_DISP_D1      39
#define GL_PIN_DISP_D2      40
#define GL_PIN_DISP_PWR_EN  45  // Strapping pin (VDD_SPI): external 10k pulldown keeps boot=LOW (3.3V)
#define GL_PIN_DISP_CLK     47
#define GL_PIN_DISP_D3      48

typedef enum {
    BRIDGE_MODE_640x400_4BPP = 0, // 128,000 B in 4x SB_SPRAM256KA (Default Full 4-bit Canvas)
    BRIDGE_MODE_640x480_2BPP = 1, // 76,800 B in 3x SB_SPRAM256KA (Full 640x480 2-bit -> 4-bit LUT)
    BRIDGE_MODE_ROI_WINDOW   = 2  // Floating 4-bit ROI window
} gl_bridge_mode_t;

typedef struct {
    gl_bridge_mode_t mode;
    int8_t           disparity_px; // -32..+32 px binocular convergence offset (default +8)
    bool             mirror_left;  // false
    bool             mirror_right; // true (compensates symmetric temple mounting)
    uint32_t         qspi_clk_hz;  // 40000000 (40 MHz)
} gl_bridge_config_t;

uint16_t gl_bridge_crc16_ccitt(const uint8_t *data, size_t len, uint16_t init_crc);
size_t   gl_bridge_rle4_compress(const uint8_t *raw_4bpp, size_t raw_len, uint8_t *out_rle, size_t max_out);
size_t   gl_bridge_build_rle4_packet(uint16_t start_waddr, const uint8_t *raw_4bpp, size_t raw_len,
                                     uint8_t *pkt_buf, size_t pkt_cap);

#endif
