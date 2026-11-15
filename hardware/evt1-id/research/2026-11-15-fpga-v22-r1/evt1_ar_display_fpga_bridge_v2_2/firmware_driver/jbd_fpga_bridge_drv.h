// SPDX-License-Identifier: MIT
// File:    firmware_driver/jbd_fpga_bridge_drv.h
// Purpose: ESP32-S3 QSPI Host Driver for EVT-1 Binocular AR FPGA Display Bridge (V2.2)
//          1. Mode enum strictly aligned 1:1 with rtl/jbd_ar_bridge_pkg.vh.
//          2. Implements OP_READ_STATUS (0x50) bidirectional QSPI status readback.

#ifndef JBD_FPGA_BRIDGE_DRV_H
#define JBD_FPGA_BRIDGE_DRV_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

// Exact GPIO assignments from Kimi R8 pinmap_hw.csv (U1 ESP32-S3-WROOM-1-N16R8 -> J4)
#define GL_PIN_DISP_RST     14  // WROOM-1 Pin 22 / QFN-56 Pin 19 -> J4:2
#define GL_PIN_DISP_CS      21  // WROOM-1 Pin 23 / QFN-56 Pin 26 -> J4:3
#define GL_PIN_DISP_D0      38  // WROOM-1 Pin 31 / QFN-56 Pin 43 -> J4:5
#define GL_PIN_DISP_D1      39  // WROOM-1 Pin 32 / QFN-56 Pin 42 -> J4:6
#define GL_PIN_DISP_D2      40  // WROOM-1 Pin 33 / QFN-56 Pin 41 -> J4:7
#define GL_PIN_DISP_PWR_EN  45  // WROOM-1 Pin 26 / QFN-56 Pin 38 -> J4:9 (VDD_SPI strap: 100k pulldown)
#define GL_PIN_DISP_CLK     47  // WROOM-1 Pin 24 / QFN-56 Pin 37 -> J4:4
#define GL_PIN_DISP_D3      48  // WROOM-1 Pin 25 / QFN-56 Pin 36 -> J4:8

// Host-to-Bridge QSPI Protocol Opcodes (matches rtl/jbd_ar_bridge_pkg.vh)
#define GL_OP_NOP             0x00u
#define GL_OP_WRITE_ROI_RAW   0x10u
#define GL_OP_WRITE_ROI_RLE4  0x11u
#define GL_OP_SET_OPTICAL_CFG 0x20u
#define GL_OP_LOAD_PANEL_LUT  0x30u
#define GL_OP_COMMIT_FRAME    0x40u
#define GL_OP_READ_STATUS     0x50u

// 4 Operating Modes — 100% bit-for-bit aligned with rtl/jbd_ar_bridge_pkg.vh
typedef enum {
    BRIDGE_MODE_640x400_4BPP      = 0, // 2'b00: 128,000 B (Banks 0..3) 4-bit grayscale shared binocular canvas
    BRIDGE_MODE_640x400_2BPP_PP   = 1, // 2'b01: 64,000 B x 2 Ping-Pong double buffer (Front=B0..1, Back=B2..3)
    BRIDGE_MODE_640x480_2BPP      = 2, // 2'b10: 76,800 B full-panel 640x480 2-bit -> 4-bit LUT expansion
    BRIDGE_MODE_STEREO_INDEP_2BPP = 3  // 2'b11: Independent Left Eye (64KB in B0..1) + Right Eye (64KB in B2..3)
} gl_bridge_mode_t;

typedef struct {
    gl_bridge_mode_t mode;
    int8_t           disparity_px; // -32..+32 px binocular convergence offset (default +8)
    bool             mirror_left;  // false
    bool             mirror_right; // true (compensates symmetric temple mounting)
    uint32_t         qspi_clk_hz;  // 40000000 (40 MHz)
} gl_bridge_config_t;

// Decoded 16-bit status word returned by OP_READ_STATUS (0x50)
typedef struct {
    bool             crc_error;         // bit 15: last packet had CRC-16 mismatch
    bool             cdc_overflow;      // bit 14: 512B CDC FIFO overflow latched
    bool             stage_overflow;    // bit 13: 1024W Stage RAM overflow latched
    bool             commit_pending;    // bit 12: frame commit waiting for VSYNC
    uint8_t          active_front_bank; // bit 11: active front buffer bank (0 or 1)
    bool             stereo_indep_mode; // bit 10: independent binocular stereo active
    gl_bridge_mode_t active_mode;       // bits 9:8: active display mode (0..3)
    uint8_t          good_pkt_cnt_lo4;  // bits 7:4: low 4 bits of valid packet counter
    uint8_t          bad_pkt_cnt_lo4;   // bits 3:0: low 4 bits of rejected packet counter
    uint16_t         raw_status_word;   // raw 16-bit status word read over QSPI D[3:0]
} gl_bridge_status_t;

// Half-duplex QSPI hardware transfer callback: transmits tx_len bytes (1 byte = 2 nibbles),
// waits dummy_cycles SCLK cycles with IO tri-stated, then reads rx_len bytes over D[3:0].
typedef int (*gl_qspi_halfduplex_xfer_fn_t)(
    const uint8_t *tx_buf, size_t tx_len,
    size_t dummy_sclk_cycles,
    uint8_t *rx_buf, size_t rx_len,
    void *user_ctx
);

uint16_t gl_bridge_crc16_ccitt(const uint8_t *data, size_t len, uint16_t init_crc);
size_t   gl_bridge_rle4_compress(const uint8_t *raw_4bpp, size_t raw_len, uint8_t *out_rle, size_t max_out);
size_t   gl_bridge_build_rle4_packet(uint16_t start_waddr, const uint8_t *raw_4bpp, size_t raw_len,
                                     uint8_t *pkt_buf, size_t pkt_cap);
size_t   gl_bridge_build_optical_cfg_packet(const gl_bridge_config_t *cfg, uint8_t *pkt_buf, size_t pkt_cap);
size_t   gl_bridge_build_commit_packet(bool swap_bank, uint8_t *pkt_buf, size_t pkt_cap);
void     gl_bridge_parse_status_word(uint16_t raw_status, gl_bridge_status_t *out_status);
int      gl_bridge_qspi_read_status(gl_qspi_halfduplex_xfer_fn_t xfer_fn, void *user_ctx,
                                    gl_bridge_status_t *out_status);

#endif
