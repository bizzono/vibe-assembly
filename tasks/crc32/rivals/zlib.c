/* A rival, not a reference: crc32() from the system's zlib, which its vendor has
 * already hand-optimized for this CPU. `vibeasm bench crc32 --rivals` times it next to
 * the solution, to show where agent-written assembly stands against expert code. */
#include <stddef.h>
#include <stdint.h>
#include <zlib.h>

uint64_t crc32_ieee(const uint8_t *buf, size_t len) {
    return crc32_z(0L, buf, len);
}
