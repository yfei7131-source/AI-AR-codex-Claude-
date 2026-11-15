// SPDX-License-Identifier: MIT
// File:    firmware_driver/jbd_fpga_bridge_drv.c
// Purpose: Portable C implementation of the ESP32-S3 -> FPGA QSPI packet builder,
//          RLE4 compressor, CRC-16-CCITT generator, optical config/commit builders,
//          and OP_READ_STATUS (0x50) bidirectional QSPI status readback driver.

#include "jbd_fpga_bridge_drv.h"
#include <string.h>

uint16_t gl_bridge_crc16_ccitt(const uint8_t *data, size_t len, uint16_t crc) {
    for (size_t i = 0; i < len; i++) {
        crc ^= ((uint16_t)data[i] << 8);
        for (int b = 0; b < 8; b++) {
            if (crc & 0x8000) crc = (uint16_t)((crc << 1) ^ 0x1021);
            else              crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

size_t gl_bridge_rle4_compress(const uint8_t *raw_4bpp, size_t raw_len, uint8_t *out_rle, size_t max_out) {
    size_t in_i = 0, out_i = 0;
    while (in_i < raw_len) {
        uint8_t val = raw_4bpp[in_i];
        size_t run = 1;
        while (in_i + run < raw_len && raw_4bpp[in_i + run] == val && run < 255) {
            run++;
        }
        if (run >= 3 || val == 0xFF) {
            if (out_i + 3 > max_out) return 0;
            out_rle[out_i++] = 0xFF;
            out_rle[out_i++] = (uint8_t)run;
            out_rle[out_i++] = val;
            in_i += run;
        } else {
            if (out_i + 1 > max_out) return 0;
            out_rle[out_i++] = val;
            in_i++;
        }
    }
    return out_i;
}

size_t gl_bridge_build_rle4_packet(uint16_t start_waddr, const uint8_t *raw_4bpp, size_t raw_len,
                                   uint8_t *pkt_buf, size_t pkt_cap) {
    if (!raw_4bpp || !pkt_buf || pkt_cap < 10) return 0;
    size_t rle_len = gl_bridge_rle4_compress(raw_4bpp, raw_len, pkt_buf + 5, pkt_cap - 7);
    if (rle_len == 0) return 0;

    pkt_buf[0] = GL_OP_WRITE_ROI_RLE4;
    pkt_buf[1] = (uint8_t)(start_waddr >> 8);
    pkt_buf[2] = (uint8_t)(start_waddr & 0xFF);
    pkt_buf[3] = (uint8_t)(rle_len >> 8);
    pkt_buf[4] = (uint8_t)(rle_len & 0xFF);

    uint16_t crc = gl_bridge_crc16_ccitt(pkt_buf, 5 + rle_len, 0xFFFF);
    pkt_buf[5 + rle_len] = (uint8_t)(crc >> 8);
    pkt_buf[6 + rle_len] = (uint8_t)(crc & 0xFF);
    return 7 + rle_len;
}

size_t gl_bridge_build_optical_cfg_packet(const gl_bridge_config_t *cfg, uint8_t *pkt_buf, size_t pkt_cap) {
    if (!cfg || !pkt_buf || pkt_cap < 6) return 0;
    if ((unsigned int)cfg->mode > (unsigned int)BRIDGE_MODE_STEREO_INDEP_2BPP) return 0;

    uint8_t mirror_mask = (cfg->mirror_left ? 0x01u : 0x00u) |
                          (cfg->mirror_right ? 0x02u : 0x00u);
    pkt_buf[0] = GL_OP_SET_OPTICAL_CFG;
    pkt_buf[1] = (uint8_t)(cfg->mode & 0x03u);
    pkt_buf[2] = (uint8_t)cfg->disparity_px;
    pkt_buf[3] = mirror_mask;

    uint16_t crc = gl_bridge_crc16_ccitt(pkt_buf, 4, 0xFFFF);
    pkt_buf[4] = (uint8_t)(crc >> 8);
    pkt_buf[5] = (uint8_t)(crc & 0xFF);
    return 6;
}

size_t gl_bridge_build_commit_packet(bool swap_bank, uint8_t *pkt_buf, size_t pkt_cap) {
    if (!pkt_buf || pkt_cap < 4) return 0;
    pkt_buf[0] = GL_OP_COMMIT_FRAME;
    pkt_buf[1] = swap_bank ? 0x01u : 0x00u;

    uint16_t crc = gl_bridge_crc16_ccitt(pkt_buf, 2, 0xFFFF);
    pkt_buf[2] = (uint8_t)(crc >> 8);
    pkt_buf[3] = (uint8_t)(crc & 0xFF);
    return 4;
}

void gl_bridge_parse_status_word(uint16_t raw_status, gl_bridge_status_t *out_status) {
    if (!out_status) return;
    out_status->raw_status_word   = raw_status;
    out_status->crc_error         = ((raw_status >> 15) & 0x01u) != 0;
    out_status->cdc_overflow      = ((raw_status >> 14) & 0x01u) != 0;
    out_status->stage_overflow    = ((raw_status >> 13) & 0x01u) != 0;
    out_status->commit_pending    = ((raw_status >> 12) & 0x01u) != 0;
    out_status->active_front_bank = (uint8_t)((raw_status >> 11) & 0x01u);
    out_status->stereo_indep_mode = ((raw_status >> 10) & 0x01u) != 0;
    out_status->active_mode       = (gl_bridge_mode_t)((raw_status >> 8) & 0x03u);
    out_status->good_pkt_cnt_lo4  = (uint8_t)((raw_status >> 4) & 0x0Fu);
    out_status->bad_pkt_cnt_lo4   = (uint8_t)(raw_status & 0x0Fu);
}

int gl_bridge_qspi_read_status(gl_qspi_halfduplex_xfer_fn_t xfer_fn, void *user_ctx,
                               gl_bridge_status_t *out_status) {
    if (!xfer_fn || !out_status) return -1;
    uint8_t cmd_byte = GL_OP_READ_STATUS;
    uint8_t rx_bytes[2] = {0, 0};
    // 1 byte opcode (2 nibbles) + 2 dummy SCLK turnaround cycles + 2 bytes (4 nibbles) status readback
    int rc = xfer_fn(&cmd_byte, 1, 2, rx_bytes, 2, user_ctx);
    if (rc != 0) return rc;
    uint16_t raw = ((uint16_t)rx_bytes[0] << 8) | (uint16_t)rx_bytes[1];
    gl_bridge_parse_status_word(raw, out_status);
    return 0;
}
