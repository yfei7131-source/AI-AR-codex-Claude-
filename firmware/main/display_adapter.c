#include "display_adapter.h"
bool gl_display_ready(const gl_display_adapter *d) { return d && d->reviewed && d->sink; }
enum gl_display_result gl_display_bitmap(const gl_display_adapter *d, const uint8_t *pixels,
                                        size_t bytes, uint16_t width, uint16_t height) {
    if (!gl_display_ready(d)) return GL_DISPLAY_UNCONFIGURED;
    if (!pixels || !width || !height || width>256 || height>256 ||
        bytes!=((size_t)width+7)/8*height) return GL_DISPLAY_INVALID_BITMAP;
    return d->sink(pixels,bytes,width,height,d->context) ? GL_DISPLAY_OK : GL_DISPLAY_IO_ERROR;
}
