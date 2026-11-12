"""Targets: the (ISA, OS) pairs the harness can assemble, verify and time for.

A target is everything that is specific to one machine family: how to assemble, which
CPU features a solution may assume, how symbols are spelled, and which trampoline
checks the calling convention. Adding a target means adding an entry here, a
trampoline in kit/, and an ABI sheet in prompts/.
"""
from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import dataclass
from typing import Dict, Tuple

from .util import ToolError, run


@dataclass(frozen=True)
class Target:
    name: str
    cc: str
    asm_flags: Tuple[str, ...]        # assembling a candidate
    c_flags: Tuple[str, ...]          # always passed when compiling C
    baseline_flags: Tuple[str, ...]   # the compiler baseline a solution must beat
    oracle_flags: Tuple[str, ...]     # the reference build used as the oracle
    shared_flags: Tuple[str, ...]
    dylib_ext: str
    symbol_prefix: str                # what the C symbol `f` is called in assembly
    tramp: str                        # kit file with the ABI-checking trampoline
    abi_sheet: str                    # prompts/ file given to the agent
    feature_baseline: str             # human description of what solutions may assume


ARM64_DARWIN = Target(
    name="arm64-darwin",
    cc="clang",
    # -mcpu=apple-m1 makes the assembler reject instructions the oldest Apple Silicon
    # Mac does not have, so a verified solution runs on every Apple Silicon Mac.
    asm_flags=("-arch", "arm64", "-mcpu=apple-m1"),
    c_flags=("-arch", "arm64", "-std=c11"),
    baseline_flags=("-O3", "-mcpu=native"),
    oracle_flags=("-O1",),
    shared_flags=("-shared",),
    dylib_ext=".dylib",
    symbol_prefix="_",
    tramp="tramp_arm64_darwin.s",
    abi_sheet="abi_arm64_darwin.md",
    feature_baseline="Apple M1 and later (ARMv8.4-A + NEON, CRC32, AES, PMULL, SHA1/2/3/512, "
                     "DotProd, FP16, LSE, RDM; no SVE/SME)",
)

ARM64_LINUX = Target(
    name="arm64-linux",
    cc="clang",
    asm_flags=("-march=armv8.2-a+crc+crypto+dotprod+fp16", "-fPIC"),
    c_flags=("-std=c11", "-fPIC"),
    baseline_flags=("-O3", "-mcpu=native"),
    oracle_flags=("-O1",),
    shared_flags=("-shared", "-fPIC"),
    dylib_ext=".so",
    symbol_prefix="",
    tramp="tramp_arm64_linux.s",
    abi_sheet="abi_arm64_linux.md",
    feature_baseline="ARMv8.2-A+ (NEON, CRC32, AES/PMULL, DotProd, FP16, LSE; AWS Graviton2/3/4, Ampere Altra)",
)

X86_64_LINUX = Target(
    name="x86_64-linux",
    cc="clang",
    asm_flags=("-march=x86-64-v3", "-fPIC"),
    c_flags=("-std=c11", "-fPIC"),
    baseline_flags=("-O3", "-march=native"),
    oracle_flags=("-O1",),
    shared_flags=("-shared", "-fPIC"),
    dylib_ext=".so",
    symbol_prefix="",
    tramp="tramp_x86_64_linux.s",
    abi_sheet="abi_x86_64_linux.md",
    feature_baseline="x86-64-v3 (AVX2, BMI1/2, FMA, LZCNT, MOVBE, POPCNT, SSE4.2, PCLMULQDQ)",
)

TARGETS: Dict[str, Target] = {t.name: t for t in (ARM64_DARWIN, ARM64_LINUX, X86_64_LINUX)}


class UnsupportedTarget(Exception):
    pass


def host_target_name() -> str:
    machine = platform.machine().lower()
    isa = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}.get(machine, machine)
    osname = {"darwin": "darwin", "linux": "linux"}.get(sys.platform, sys.platform)
    return "%s-%s" % (isa, osname)


def detect(name: str = "") -> Target:
    name = name or host_target_name()
    if name not in TARGETS:
        raise UnsupportedTarget(
            "target '%s' is not supported yet. Supported: %s.\n"
            "Assembly is verified by running it, so a target needs a trampoline, an ABI sheet and a "
            "machine to run on. See docs/ADDING_A_TARGET.md." % (name, ", ".join(sorted(TARGETS))))
    return TARGETS[name]


def describe_host() -> Dict[str, str]:
    """Facts about this machine, recorded with every result."""
    info: Dict[str, str] = {"target": host_target_name()}

    def first_line(cmd):
        try:
            code, out, _ = run(cmd, timeout=10)
            return out.strip().splitlines()[0] if code == 0 and out.strip() else ""
        except (ToolError, OSError):
            return ""

    if sys.platform == "darwin":
        info["cpu"] = first_line(["sysctl", "-n", "machdep.cpu.brand_string"])
        info["os"] = "macOS " + first_line(["sw_vers", "-productVersion"])
    else:
        info["cpu"] = platform.processor() or platform.machine()
        info["os"] = platform.platform()
    if shutil.which("clang"):
        info["cc"] = first_line(["clang", "--version"])
    return info
