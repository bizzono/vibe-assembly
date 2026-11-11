#!/usr/bin/env python3
"""The shootout: the same six kernels in every language, timed the same way.

    shootout/shootout.py                       build and run everything that is installed
    shootout/shootout.py --langs c,rust,asm    a subset of languages
    shootout/shootout.py --kernels crc32       a subset of kernels
    shootout/shootout.py --quick               one short launch each (smoke test)

Every entry follows shootout/PROTOCOL.md. An entry whose result or digest differs
from the C reference is reported as WRONG and left out of the tables. Languages whose
toolchain is not installed are skipped.

Results go to shootout/results/results.json (+ RESULTS.md).
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from vibeasm.build import Builder          # noqa: E402
from vibeasm.target import describe_host, detect, UnsupportedTarget   # noqa: E402
from vibeasm.task import load_task         # noqa: E402

LANGS_DIR = HERE / "langs"
BUILD = HERE / "build"
RESULTS = HERE / "results"

MIB = 1 << 20

# kernel -> what goes in its input file
KERNELS = OrderedDict([
    ("wordcount", {"title": "Word count", "input": "8 MiB of text", "size": 8 * MIB, "flavor": 0}),
    ("utf8_validate", {"title": "UTF-8 validation", "input": "8 MiB of mixed-script UTF-8", "size": 8 * MIB, "flavor": 0}),
    ("crc32", {"title": "CRC-32", "input": "8 MiB of random bytes", "size": 8 * MIB, "flavor": 0}),
    ("base64_encode", {"title": "Base64 encode", "input": "6 MiB of random bytes", "size": 6 * MIB, "flavor": 0}),
    ("mandelbrot", {"title": "Mandelbrot", "input": "512 x 512 pixels, 200 iterations", "args": [512, 512, 200]}),
    ("nqueens", {"title": "N-queens", "input": "12 x 12 board", "args": [12]}),
])


class Skip(Exception):
    """This language (or this kernel in it) cannot be built here."""


def sh(cmd, cwd=None, timeout=900, env=None) -> str:
    p = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                       errors="replace", timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError("%s\n%s" % (" ".join(str(c) for c in cmd), (p.stderr or p.stdout).strip()[-3000:]))
    return p.stdout


def tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise Skip("%s not found on PATH" % name)
    return path


def first_line(cmd) -> str:
    try:
        p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=60)
        text = (p.stdout or p.stderr).strip()
        return text.splitlines()[0].strip() if text else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def copy_to(src: Path, dst: Path) -> Path:
    if not src.is_file():
        raise Skip("no %s" % src.relative_to(HERE))
    shutil.copyfile(src, dst)
    return dst


def kernel_cflags(kernel: str) -> List[str]:
    return list(load_task(ROOT, kernel).cflags)


# ---- languages -------------------------------------------------------------------------
# Each builder returns the command line (without the input file and min_ms arguments).

def build_asm(kernel: str, bdir: Path) -> List[str]:
    try:
        target = detect()
    except UnsupportedTarget as e:
        raise Skip(str(e).splitlines()[0])
    solution = ROOT / "solutions" / target.name / (kernel + ".s")
    if not solution.is_file():
        raise Skip("no verified solution yet (run `vibeasm run %s`)" % kernel)
    d = LANGS_DIR / "asm"
    sh([tool(target.cc), *target.asm_flags, d / "main.s", d / (kernel + ".s"), solution, "-o", bdir / "prog"])
    return [str(bdir / "prog")]


def build_c(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "c"
    sh([tool("clang"), "-std=c11", "-O3", "-mcpu=native", *kernel_cflags(kernel), d / "main.c", d / (kernel + ".c"),
        "-o", bdir / "prog"])
    return [str(bdir / "prog")]


def build_cpp(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "cpp"
    if not (d / (kernel + ".cpp")).is_file():
        raise Skip("no langs/cpp/%s.cpp" % kernel)
    sh([tool("clang++"), "-std=c++20", "-O3", "-mcpu=native", *kernel_cflags(kernel), d / "main.cpp",
        d / (kernel + ".cpp"), "-o", bdir / "prog"])
    return [str(bdir / "prog")]


def build_rust(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "rust"
    copy_to(d / "main.rs", bdir / "main.rs")
    copy_to(d / (kernel + ".rs"), bdir / "kernel.rs")
    sh([tool("rustc"), "--edition", "2021", "-C", "opt-level=3", "-C", "target-cpu=native", "-C", "codegen-units=1",
        "-C", "panic=abort", "main.rs", "-o", "prog"], cwd=bdir)
    return [str(bdir / "prog")]


def build_zig(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "zig"
    copy_to(d / "main.zig", bdir / "main.zig")
    copy_to(d / (kernel + ".zig"), bdir / "kernel.zig")
    env = dict(os.environ, ZIG_LOCAL_CACHE_DIR=str(bdir / ".zig-cache"), ZIG_GLOBAL_CACHE_DIR=str(BUILD / ".zig-global"))
    sh([tool("zig"), "build-exe", "main.zig", "-O", "ReleaseFast", "-mcpu=native", "--name", "prog"], cwd=bdir, env=env)
    return [str(bdir / "prog")]


def build_go(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "go"
    copy_to(d / "main.go", bdir / "main.go")
    copy_to(d / (kernel + ".go"), bdir / "kernel.go")
    (bdir / "go.mod").write_text("module shootout\n\ngo 1.21\n")
    env = dict(os.environ, GOFLAGS="-mod=mod", GOWORK="off")
    sh([tool("go"), "build", "-o", "prog", "."], cwd=bdir, env=env)
    return [str(bdir / "prog")]


def build_swift(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "swift"
    copy_to(d / "main.swift", bdir / "main.swift")
    copy_to(d / (kernel + ".swift"), bdir / "kernel.swift")
    sh([tool("swiftc"), "-O", "-wmo", "main.swift", "kernel.swift", "-o", "prog"], cwd=bdir)
    return [str(bdir / "prog")]


def build_java(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "java"
    copy_to(d / "Main.java", bdir / "Main.java")
    copy_to(d / (kernel + ".java"), bdir / "Kernel.java")
    java = tool("java")
    if "Unable to locate" in first_line([java, "-version"]):
        raise Skip("no Java runtime installed")
    sh([tool("javac"), "-d", "classes", "Main.java", "Kernel.java"], cwd=bdir)
    return [java, "-cp", str(bdir / "classes"), "Main"]


def build_csharp(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "csharp"
    copy_to(d / "Program.cs", bdir / "Program.cs")
    copy_to(d / (kernel + ".cs"), bdir / "Kernel.cs")
    copy_to(d / "shootout.csproj", bdir / "shootout.csproj")
    dotnet = tool("dotnet")
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
    sh([dotnet, "build", "-c", "Release", "-o", "out", "--nologo", "-v", "q"], cwd=bdir, env=env)
    return [dotnet, str(bdir / "out" / "shootout.dll")]


def build_js(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "js"
    if not (d / (kernel + ".js")).is_file():
        raise Skip("no langs/js/%s.js" % kernel)
    return [tool("node"), str(d / "main.js"), str(d / (kernel + ".js"))]


def build_python(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "python"
    if not (d / (kernel + ".py")).is_file():
        raise Skip("no langs/python/%s.py" % kernel)
    return [tool("python3"), str(d / "main.py"), str(d / (kernel + ".py"))]


def build_ruby(kernel: str, bdir: Path) -> List[str]:
    d = LANGS_DIR / "ruby"
    if not (d / (kernel + ".rb")).is_file():
        raise Skip("no langs/ruby/%s.rb" % kernel)
    ruby = tool("ruby")
    yjit = ["--yjit"] if ruby_has_yjit(ruby) else []
    return [ruby, *yjit, str(d / "main.rb"), str(d / (kernel + ".rb"))]


def ruby_has_yjit(ruby: str) -> bool:
    try:
        return subprocess.run([ruby, "--yjit", "-e", "exit(RubyVM::YJIT.enabled? ? 0 : 1)"], capture_output=True,
                              timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


LANGS = OrderedDict([
    ("asm", {"name": "Assembly", "note": "written by the agent harness; no compiler", "build": build_asm,
             "version": lambda: "vibe-assembly solutions (%s)" % detect().name}),
    ("c", {"name": "C", "note": "clang -O3 -mcpu=native", "build": build_c,
           "version": lambda: first_line(["clang", "--version"])}),
    ("cpp", {"name": "C++", "note": "clang++ -O3 -mcpu=native", "build": build_cpp,
             "version": lambda: first_line(["clang++", "--version"])}),
    ("rust", {"name": "Rust", "note": "rustc -C opt-level=3 -C target-cpu=native", "build": build_rust,
              "version": lambda: first_line(["rustc", "--version"])}),
    ("zig", {"name": "Zig", "note": "ReleaseFast, -mcpu=native", "build": build_zig,
             "version": lambda: "zig " + first_line(["zig", "version"])}),
    ("go", {"name": "Go", "note": "go build", "build": build_go,
            "version": lambda: first_line(["go", "version"])}),
    ("swift", {"name": "Swift", "note": "swiftc -O", "build": build_swift,
               "version": lambda: first_line(["swiftc", "--version"])}),
    ("java", {"name": "Java", "note": "HotSpot JIT, after warm-up", "build": build_java,
              "version": lambda: first_line(["java", "--version"])}),
    ("csharp", {"name": "C#", "note": ".NET JIT, after warm-up", "build": build_csharp,
                "version": lambda: ".NET " + first_line(["dotnet", "--version"])}),
    ("js", {"name": "JavaScript", "note": "Node.js (V8 JIT), after warm-up", "build": build_js,
            "version": lambda: "node " + first_line(["node", "--version"])}),
    ("python", {"name": "Python", "note": "CPython", "build": build_python,
                "version": lambda: first_line(["python3", "--version"])}),
    ("ruby", {"name": "Ruby", "note": "CRuby, YJIT on when the build has it", "build": build_ruby,
              "version": lambda: first_line(["ruby", "--version"]) +
              (" +YJIT" if shutil.which("ruby") and ruby_has_yjit(shutil.which("ruby")) else "")}),
])


# ---- inputs ---------------------------------------------------------------------------------

def make_inputs(kernels: List[str]) -> Dict[str, Path]:
    out = {}
    builder = Builder(ROOT, detect())
    (BUILD / "inputs").mkdir(parents=True, exist_ok=True)
    for k in kernels:
        cfg = KERNELS[k]
        path = BUILD / "inputs" / (k + ".bin")
        if "args" in cfg:
            path.write_bytes(struct.pack("<%dI" % len(cfg["args"]), *cfg["args"]))
        elif not path.exists() or path.stat().st_size != cfg["size"]:
            task = load_task(ROOT, k)
            sh([builder.driver(task), "gen", cfg["size"], cfg["flavor"], 20260101, path])
        out[k] = path
    return out


# ---- running ----------------------------------------------------------------------------------

def run_entry(cmd: List[str], input_path: Path, min_ms: int, timeout: int = 900):
    """One launch. Returns (result, digest, best_ns, calls, wall_seconds)."""
    t0 = time.perf_counter()
    p = subprocess.run(cmd + [str(input_path), str(min_ms)], capture_output=True, text=True, errors="replace",
                       timeout=timeout)
    wall = time.perf_counter() - t0
    if p.returncode != 0:
        raise RuntimeError("exit %d: %s" % (p.returncode, (p.stderr or p.stdout).strip()[-500:]))
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) == 5 and parts[0] == "RESULT":
            return int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]), wall
    raise RuntimeError("no RESULT line in output: %r" % p.stdout[-300:])


def measure(cmd: List[str], input_path: Path, launches: int, min_ms: int, cold_launches: int):
    best, calls, result, digest = None, 0, None, None
    for _ in range(launches):
        r, d, ns, c, _wall = run_entry(cmd, input_path, min_ms)
        if result is None:
            result, digest = r, d
        elif (r, d) != (result, digest):
            raise RuntimeError("result differs between launches")
        best = ns if best is None else min(best, ns)
        calls += c
    cold = None
    for _ in range(cold_launches):
        r, _d, _ns, _c, wall = run_entry(cmd, input_path, 0)
        if r != result:
            raise RuntimeError("cold run gives a different result")
        cold = wall if cold is None else min(cold, wall)
    return {"result": result, "digest": digest, "best_ns": best, "calls": calls,
            "cold_ms": round(cold * 1e3, 3) if cold is not None else None}


def fmt_time(ns: float) -> str:
    if ns < 1e6:
        return "%.0f us" % (ns / 1e3)
    if ns < 1e9:
        return "%.2f ms" % (ns / 1e6) if ns < 1e8 else "%.0f ms" % (ns / 1e6)
    return "%.2f s" % (ns / 1e9)


def geomean(vals: List[float]) -> float:
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) if vals else 0.0


def write_markdown(res: dict, path: Path) -> None:
    langs = [l for l in res["langs"] if any(l in k["entries"] for k in res["kernels"].values())]
    kernels = list(res["kernels"])
    lines = ["# Shootout results", "",
             "%s, %s. %s." % (res["host"].get("cpu", "?"), res["host"].get("os", "?"), res["date"]),
             "Time for one call of the kernel (minimum over many calls, after warm-up); lower is better. "
             "The multiplier is relative to the assembly entry.", ""]
    head = ["language"] + [res["kernels"][k]["title"] for k in kernels] + ["geomean vs asm"]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("|" + "|".join(["---"] + ["---:"] * (len(head) - 1)) + "|")
    for l in langs:
        row, ratios = ["**%s**" % res["langs"][l]["name"]], []
        for k in kernels:
            e = res["kernels"][k]["entries"].get(l)
            asm = res["kernels"][k]["entries"].get("asm")
            if not e or not e.get("ok"):
                row.append("wrong" if e and e.get("error") == "wrong result" else "-")
                continue
            cell = fmt_time(e["best_ns"])
            if asm and asm.get("ok"):
                r = e["best_ns"] / asm["best_ns"]
                ratios.append(r)
                cell += " (%.1fx)" % r if l != "asm" else ""
            row.append(cell)
        row.append("%.1fx" % geomean(ratios) if ratios and l != "asm" and len(ratios) == len(kernels) else
                   ("1.0x" if l == "asm" else "-"))
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Cold runs", "",
              "Wall time of one whole process that runs the kernel once: start-up, reading the input, one call, exit.",
              ""]
    lines.append("| " + " | ".join(["language"] + [res["kernels"][k]["title"] for k in kernels]) + " |")
    lines.append("|" + "|".join(["---"] + ["---:"] * len(kernels)) + "|")
    for l in langs:
        row = ["**%s**" % res["langs"][l]["name"]]
        for k in kernels:
            e = res["kernels"][k]["entries"].get(l)
            row.append("%.1f ms" % e["cold_ms"] if e and e.get("ok") and e.get("cold_ms") is not None else "-")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Inputs and toolchains", ""]
    for k in kernels:
        lines.append("- **%s**: %s." % (res["kernels"][k]["title"], res["kernels"][k]["input"]))
    lines.append("")
    for l in langs:
        lines.append("- **%s**: %s (%s)" % (res["langs"][l]["name"], res["langs"][l]["version"], res["langs"][l]["note"]))
    lines += ["", "Every entry printed the same result as the C reference for every kernel, or it is marked `wrong`.",
              "Rules and method: [PROTOCOL.md](../PROTOCOL.md).", ""]
    path.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--langs", default="", help="comma-separated subset (default: all installed)")
    ap.add_argument("--kernels", default="", help="comma-separated subset (default: all)")
    ap.add_argument("--min-ms", type=int, default=1500, help="timed work per launch (default 1500)")
    ap.add_argument("--launches", type=int, default=5, help="process launches per entry; the best is kept (default 5)")
    ap.add_argument("--cold", type=int, default=7, help="cold launches per entry (default 7)")
    ap.add_argument("--quick", action="store_true", help="smoke test: one 200 ms launch, one cold launch")
    ap.add_argument("--no-write", action="store_true", help="do not write results/")
    ap.add_argument("--merge", action="store_true", help="update the existing results.json instead of replacing it")
    args = ap.parse_args()
    if args.quick:
        args.min_ms, args.launches, args.cold = 200, 1, 1

    for extra in (ROOT / ".toolchains" / "bin", Path.home() / ".dotnet"):
        if extra.is_dir():
            os.environ["PATH"] = str(extra) + os.pathsep + os.environ["PATH"]

    langs = [l for l in (args.langs.split(",") if args.langs else LANGS) if l]
    kernels = [k for k in (args.kernels.split(",") if args.kernels else KERNELS) if k]
    for l in langs:
        if l not in LANGS:
            ap.error("unknown language %s (known: %s)" % (l, ", ".join(LANGS)))
    for k in kernels:
        if k not in KERNELS:
            ap.error("unknown kernel %s (known: %s)" % (k, ", ".join(KERNELS)))
    if "c" not in langs:
        langs = ["c"] + langs       # C is the correctness reference for everything else

    # One shootout at a time: concurrent runs would rebuild each other's binaries and
    # disturb each other's timings.
    import fcntl
    BUILD.mkdir(exist_ok=True)
    lock = open(BUILD / ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another shootout is running; waiting for it to finish...", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)

    inputs = make_inputs(kernels)
    res = {"date": datetime.date.today().isoformat(), "host": describe_host(),
           "method": {"min_ms": args.min_ms, "launches": args.launches, "cold_launches": args.cold,
                      "metric": "minimum time of one kernel call, ns"},
           "langs": OrderedDict(), "kernels": OrderedDict()}
    if args.merge and (RESULTS / "results.json").exists():
        old = json.loads((RESULTS / "results.json").read_text(), object_pairs_hook=OrderedDict)
        res["langs"], res["kernels"] = old.get("langs", OrderedDict()), old.get("kernels", OrderedDict())

    for l in langs:
        res["langs"][l] = {"name": LANGS[l]["name"], "note": LANGS[l]["note"], "version": LANGS[l]["version"]()}
    for k in kernels:
        res["kernels"].setdefault(k, {"title": KERNELS[k]["title"], "input": KERNELS[k]["input"], "entries": OrderedDict()})

    failures = 0
    for k in kernels:
        print("\n== %s (%s)" % (KERNELS[k]["title"], KERNELS[k]["input"]), flush=True)
        entries = res["kernels"][k]["entries"]
        ref = None
        for l in sorted(langs, key=lambda x: x != "c"):       # C first: it defines the right answer
            bdir = BUILD / l / k
            shutil.rmtree(bdir, ignore_errors=True)
            bdir.mkdir(parents=True, exist_ok=True)
            try:
                cmd = LANGS[l]["build"](k, bdir)
                m = measure(cmd, inputs[k], args.launches, args.min_ms, args.cold)
            except Skip as e:
                print("  %-11s skipped: %s" % (LANGS[l]["name"], e), flush=True)
                entries.pop(l, None)
                continue
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                print("  %-11s FAILED: %s" % (LANGS[l]["name"], str(e).strip().splitlines()[-1][:160]), flush=True)
                entries[l] = {"ok": False, "error": str(e)[-400:]}
                failures += 1
                continue
            if l == "c":
                ref = (m["result"], m["digest"])
            m["ok"] = ref is not None and (m["result"], m["digest"]) == ref
            if not m["ok"]:
                m["error"] = "wrong result"
                failures += 1
            entries[l] = m
            print("  %-11s %10s   cold %7.1f ms   %s" % (
                LANGS[l]["name"], fmt_time(m["best_ns"]), m["cold_ms"] or 0,
                "ok (result %d)" % m["result"] if m["ok"] else
                "WRONG: got %s/%s, C says %s/%s" % (m["result"], m["digest"], ref[0] if ref else "?", ref[1] if ref else "?")),
                  flush=True)
        # keep the canonical language order in the file
        res["kernels"][k]["entries"] = OrderedDict((l, entries[l]) for l in LANGS if l in entries)

    res["langs"] = OrderedDict((l, res["langs"][l]) for l in LANGS if l in res["langs"])
    if not args.no_write:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "results.json").write_text(json.dumps(res, indent=1) + "\n")
        write_markdown(res, RESULTS / "RESULTS.md")
        print("\nwrote %s and RESULTS.md" % (RESULTS / "results.json").relative_to(ROOT))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
