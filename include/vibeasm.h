/*
 * vibeasm.h -- Public C/C++ SDK header for vibe-assembly verified kernels.
 *
 * SPDX-License-Identifier: MIT
 *
 * Every function declared in this header is backed by a verified assembly
 * implementation in `solutions/<target>/` (with automatic C reference fallback
 * on platforms without an installed assembly solution).
 *
 * Guarantees enforced by the vibe-assembly verification harness:
 *   1. Pure leaf execution: zero heap allocations, zero mutable global/static
 *      state, thread-safe and re-entrant across arbitrary concurrent callers.
 *   2. Strict ABI compliance: preserves all callee-saved general and SIMD/FP
 *      registers, stack pointer alignment, and red-zone invariants.
 *   3. Page-boundary safety: verified against PROT_NONE mmap guard pages on
 *      both ends of every input and output buffer (zero over-read/over-write).
 *   4. Differential equivalence: verified against the C reference implementation
 *      across hundreds of thousands of edge-case and fuzz inputs.
 */

#ifndef VIBEASM_H
#define VIBEASM_H

#include <stddef.h>
#include <stdint.h>

#define VIBEASM_VERSION_MAJOR 0
#define VIBEASM_VERSION_MINOR 1
#define VIBEASM_VERSION_PATCH 0
#define VIBEASM_VERSION_STRING "0.1.0"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Return the vibe-assembly library version string (e.g. "0.1.0").
 */
const char *vibeasm_version(void);

/**
 * Count ASCII whitespace-separated words in `buf` of length `len` bytes.
 *
 * Whitespace is defined as ASCII space (0x20) and control characters 0x09..0x0d
 * ('\t', '\n', '\v', '\f', '\r'). Equivalent to `wc -w` on arbitrary byte streams.
 *
 * @param buf  Pointer to input bytes (may be NULL if len == 0).
 * @param len  Number of bytes in `buf`.
 * @return     Number of whitespace-delimited words in `buf`.
 */
size_t wordcount(const uint8_t *buf, size_t len);

/**
 * Validate whether `buf` of length `len` bytes is well-formed UTF-8 (RFC 3629).
 *
 * Rejects overlong encodings, surrogate code points (U+D800..U+DFFF), code points
 * above U+10FFFF, and truncated or stray continuation sequences.
 *
 * @param buf  Pointer to input bytes (may be NULL if len == 0).
 * @param len  Number of bytes in `buf`.
 * @return     1 if `buf[0..len)` is valid UTF-8, 0 otherwise.
 */
int utf8_validate(const uint8_t *buf, size_t len);

/**
 * Compute the IEEE 802.3 CRC-32 checksum (polynomial 0xEDB88320, initial value 0)
 * of `buf` of length `len` bytes (used by Ethernet, gzip, PNG, and zlib).
 *
 * @param buf  Pointer to input bytes (may be NULL if len == 0).
 * @param len  Number of bytes in `buf`.
 * @return     32-bit unsigned CRC-32 checksum.
 */
uint32_t crc32_ieee(const uint8_t *buf, size_t len);

/**
 * Encode `len` bytes from `src` into standard RFC 4648 Base64 (with '=' padding)
 * into `dst`.
 *
 * Caller must provide at least `((len + 2) / 3) * 4` bytes of capacity at `dst`.
 * Does not write a trailing NUL terminator.
 *
 * @param src  Pointer to input bytes (may be NULL if len == 0).
 * @param len  Number of input bytes to encode.
 * @param dst  Pointer to output buffer of capacity >= ((len + 2) / 3) * 4 bytes.
 * @return     Number of Base64 bytes written to `dst` (`((len + 2) / 3) * 4`).
 */
size_t base64_encode(const uint8_t *src, size_t len, uint8_t *dst);

/**
 * Compute the sum of escape-time iteration counts over a `width` x `height`
 * grid of the Mandelbrot set in IEEE-754 double precision:
 *   cr = -2.0 + x * (2.5 / width),   x in 0 .. width - 1
 *   ci = -1.25 + y * (2.5 / height), y in 0 .. height - 1
 *
 * @param width     Grid width in pixels (if <= 0, returns 0).
 * @param height    Grid height in pixels (if <= 0, returns 0).
 * @param max_iter  Maximum iterations per point (if <= 0, returns 0).
 * @return          Total escape-time iterations summed across all pixels.
 */
uint64_t mandelbrot(int64_t width, int64_t height, int64_t max_iter);

/**
 * Count the exact number of valid N-Queens placements on an `n` x `n` chessboard.
 *
 * @param n  Board dimension (for n <= 0 or n == 2 or n == 3, returns 0; for n == 1, returns 1).
 * @return   Total number of distinct non-attacking queen configurations.
 */
uint64_t nqueens(int64_t n);

#ifdef __cplusplus
}
#endif

#endif /* VIBEASM_H */
