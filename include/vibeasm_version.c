/*
 * vibeasm_version.c -- Runtime version symbol for libvibeasm.
 *
 * SPDX-License-Identifier: MIT
 */
#include "vibeasm.h"

const char *vibeasm_version(void) {
    return VIBEASM_VERSION_STRING;
}
