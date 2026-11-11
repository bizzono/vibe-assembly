"""Small shared helpers: subprocess wrapper, hashing, formatting."""
from __future__ import annotations

import hashlib
import math
import os
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


class ToolError(Exception):
    """A toolchain command failed. `output` is what the tool printed."""

    def __init__(self, message: str, output: str = ""):
        super().__init__(message)
        self.output = output


def run(cmd: Sequence[str], *, cwd: Optional[Path] = None, timeout: Optional[float] = None,
        env: Optional[dict] = None, input_text: Optional[str] = None) -> Tuple[int, str, str]:
    """Run a command, return (exit code, stdout, stderr). Never raises on non-zero exit."""
    try:
        p = subprocess.run(list(map(str, cmd)), cwd=str(cwd) if cwd else None, timeout=timeout,
                           env=env, input=input_text, capture_output=True, text=True, errors="replace")
    except FileNotFoundError:
        raise ToolError("command not found: %s" % cmd[0])
    return p.returncode, p.stdout, p.stderr


def must(cmd: Sequence[str], *, what: str, cwd: Optional[Path] = None,
         timeout: Optional[float] = None) -> str:
    """Run a command that is expected to succeed; raise ToolError with its output if not."""
    try:
        code, out, err = run(cmd, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ToolError("%s timed out" % what)
    if code != 0:
        raise ToolError("%s failed (exit %d)" % (what, code), (err or out).strip())
    return out


def sha256_hex(parts: Iterable[bytes]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(len(p).to_bytes(8, "little"))
        h.update(p)
    return h.hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geomean(values: Sequence[float]) -> float:
    vals = [v for v in values if v > 0]
    if not vals:
        return 0.0
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def fmt_ns(ns: float) -> str:
    if ns < 1e3:
        return "%.1f ns" % ns
    if ns < 1e6:
        return "%.2f us" % (ns / 1e3)
    if ns < 1e9:
        return "%.2f ms" % (ns / 1e6)
    return "%.2f s" % (ns / 1e9)


def fmt_rate(nbytes: int, ns: float) -> str:
    """Throughput for a byte-oriented kernel."""
    if ns <= 0 or nbytes <= 0:
        return ""
    gbps = nbytes / ns  # bytes per ns == GB/s
    if gbps >= 1:
        return "%.1f GB/s" % gbps
    return "%.0f MB/s" % (gbps * 1e3)


def fmt_size(n: int) -> str:
    for unit, div in (("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= div and n % div == 0:
            return "%d %s" % (n // div, unit)
    return "%d B" % n


def table(rows: List[List[str]], align: Optional[str] = None) -> str:
    """Plain-text table. `align` is a string of 'l'/'r' per column."""
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    widths = [0] * ncol
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(c))
    align = align or "l" * ncol
    out = []
    for r in rows:
        cells = []
        for i in range(ncol):
            c = r[i] if i < len(r) else ""
            cells.append(c.rjust(widths[i]) if align[i] == "r" else c.ljust(widths[i]))
        out.append("  ".join(cells).rstrip())
    return "\n".join(out)


def clean_env() -> dict:
    """Environment for child tools: no locale surprises."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    return env
