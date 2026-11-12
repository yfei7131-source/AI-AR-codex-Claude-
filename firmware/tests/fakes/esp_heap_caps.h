#ifndef TEST_HEAP_CAPS_H
#define TEST_HEAP_CAPS_H
#include <stddef.h>
#define MALLOC_CAP_SPIRAM 1
size_t heap_caps_get_total_size(unsigned caps);
#endif
