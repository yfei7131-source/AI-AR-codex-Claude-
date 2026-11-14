// SPDX-License-Identifier: MIT
// File:    firmware_driver/jbd_fpga_bridge_drv.c
// Purpose: Portable C implementation of the ESP32-S3 -> FPGA QSPI packet builder,
//          RLE4 compressor, and CRC-16-CCITT generator (compiles on both ESP-IDF & host GCC).

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
    if (pkt_cap < 10) return 0;
    size_t rle_len = gl_bridge_rle4_compress(raw_4bpp, raw_len, pkt_buf + 5, pkt_cap - 7);
    if (rle_len == 0) return 0;

    pkt_buf[0] = 0x11; // OP_WRITE_ROI_RLE4
    pkt_buf[1] = (uint8_t)(start_waddr >> 8);
    pkt_buf[2] = (uint8_t)(start_waddr & 0xFF);
    pkt_buf[3] = (uint8_t)(rle_len >> 8);
    pkt_buf[4] = (uint8_t)(rle_len & 0xFF);

    uint16_t crc = gl_bridge_crc16_ccitt(pkt_buf, 5 + rle_len, 0xFFFF);
    pkt_buf[5 + rle_len] = (uint8_t)(crc >> 8);
    pkt_buf[6 + rle_len] = (uint8_t)(crc & 0xFF);
    return 7 + rle_len;
}
