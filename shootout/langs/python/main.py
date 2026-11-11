#!/usr/bin/env python3
"""Shootout driver (Python). See shootout/PROTOCOL.md.

    python3 main.py <kernel.py> <input-file> <min_ms>

The kernel is a module defining run(data: bytes) -> int and digest() -> int.
"""
import sys

sys.dont_write_bytecode = True  # keep __pycache__ out of the source tree

import importlib.util
import time

U64 = 0xFFFFFFFFFFFFFFFF


def load_kernel(path):
    spec = importlib.util.spec_from_file_location("kernel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv):
    if len(argv) != 4:
        sys.stderr.write("usage: %s <kernel.py> <input-file> <min_ms>\n" % argv[0])
        return 2
    kernel = load_kernel(argv[1])
    with open(argv[2], "rb") as f:
        data = f.read()
    min_ns = int(argv[3]) * 1000000

    run = kernel.run
    now = time.perf_counter_ns

    if min_ns == 0:  # cold mode: one call, no digest
        t0 = now()
        result = run(data)
        best = now() - t0
        print("RESULT %d 0 %d 1" % (result & U64, best))
        return 0

    warm = run(data)
    result = warm
    best = None
    total = 0
    calls = 0
    while calls < 3 or (total < min_ns and calls < 1000000):
        t0 = now()
        result = run(data)
        dt = now() - t0
        if result != warm:
            sys.stderr.write("result changed between calls\n")
            return 3
        if best is None or dt < best:
            best = dt
        total += dt
        calls += 1
    print("RESULT %d %d %d %d" % (result & U64, kernel.digest() & U64, best, calls))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
