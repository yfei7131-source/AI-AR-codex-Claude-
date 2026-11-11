#ifndef GL_DISPLAY_ADAPTER_H
#define GL_DISPLAY_ADAPTER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Phone rasterizes Chinese. No native UTF-8 font or ESP32-S3 MIPI link is assumed. */
enum gl_display_result { GL_DISPLAY_OK=0, GL_DISPLAY_UNCONFIGURED=1, GL_DISPLAY_INVALID_BITMAP=2, GL_DISPLAY_IO_ERROR=3 };
typedef bool (*gl_bitmap_sink)(const uint8_t *pixels, size_t bytes, uint16_t width, uint16_t height, void *context);
typedef struct { bool reviewed; gl_bitmap_sink sink; void *context; } gl_display_adapter;
bool gl_display_ready(const gl_display_adapter *display);
enum gl_display_result gl_display_bitmap(const gl_display_adapter *display, const uint8_t *pixels,
                                        size_t bytes, uint16_t width, uint16_t height);
#endif
