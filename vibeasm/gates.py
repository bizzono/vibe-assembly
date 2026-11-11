"""The gates a candidate must pass, in order:

    assemble -> lint -> differential fuzz (guard pages + ABI trampoline)

`check()` runs them and returns a report written to be read by an agent: what
failed, on which input, at which source line, with which register values, and how to
reproduce it.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .build import BuildError, Builder, Candidate
from .lint import LintResult, lint_object, lint_source
from .task import Task
from .util import ToolError, clean_env, run


@dataclass
class CheckResult:
    ok: bool
    stage: str                   # "assemble" | "link" | "lint" | "fuzz" | "internal" | "passed"
    summary: str                 # one line
    detail: str = ""             # the full report for the agent
    cases: int = 0
    seed: int = 0
    profile: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        head = ("PASS  " if self.ok else "FAIL  ") + self.summary
        return head + ("\n" + self.detail if self.detail else "")


def parse_events(stdout: str) -> List[Dict[str, Any]]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def _listing_with_lines(builder: Builder, cand: Candidate):
    """[(address, text, source_line)] from the debug object's disassembly."""
    rows, line_no = [], None
    for raw in builder.disassemble(cand.dbg_obj if cand.dbg_obj.exists() else cand.obj, with_lines=True).splitlines():
        m = re.match(r";\s.*:(\d+)\s*$", raw)
        if m:
            line_no = int(m.group(1))
            continue
        m = re.match(r"\s*([0-9a-f]+):\s+(.*)$", raw)
        if m:
            rows.append((int(m.group(1), 16), m.group(2).strip().replace("\t", " "), line_no))
    return rows


def _symbol_address(obj: Path, name: str) -> Optional[int]:
    try:
        code, out, _ = run(["nm", obj])
    except ToolError:
        return None
    if code != 0:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in (name, "_" + name):
            return int(parts[0], 16)
    return None


def _annotate_reg(value: int, ev: Dict[str, Any]) -> str:
    def near(ptr_key, len_key, label):
        if ptr_key not in ev:
            return None
        base, n = int(ev[ptr_key], 16), int(ev.get(len_key, 0))
        if base - 1024 <= value <= base + n + 1024:
            off = value - base
            where = ""
            if off == n:
                where = " (one past the end)"
            elif off > n:
                where = " (%d past the end)" % (off - n)
            elif off < 0:
                where = " (before the start)"
            return "%s%+d%s" % (label, off, where)
        return None

    return near("in_ptr", "in_len", "in") or near("out_ptr", "out_cap", "out") or ""


def _crash_report(builder: Builder, task: Task, cand: Candidate, ev: Dict[str, Any], shown_name: str) -> str:
    lines = []
    phase = ev.get("phase", "?")
    if phase != "candidate":
        lines.append("  The crash happened in the %s, not in your code -- this is a bug in the TASK "
                     "(ref.c / gen.c), not in the solution." % ("reference implementation" if phase == "oracle" else phase))
    lines.append("  what:   %s" % ev.get("note", ""))
    lines.append("  signal: %s   fault address: %s" % (ev.get("signal"), ev.get("fault_addr")))
    if task.is_bytes:
        lines.append("  input:  case #%s  len=%s  flavor=%s  placement=%s (buffer flush against a guard page)"
                     % (ev.get("case"), ev.get("len"), ev.get("flavor_name"), ev.get("placement")))
    else:
        lines.append("  input:  case #%s  args=%s  flavor=%s" % (ev.get("case"), ev.get("args"), ev.get("flavor_name")))

    # map the faulting pc to a source line
    if ev.get("pc_in_candidate"):
        sym, off = ev.get("pc_symbol", ""), int(ev.get("pc_offset", 0))
        base = _symbol_address(cand.dbg_obj if cand.dbg_obj.exists() else cand.obj, sym)
        rows = _listing_with_lines(builder, cand)
        if base is not None and rows:
            addr = base + off
            idx = next((i for i, r in enumerate(rows) if r[0] == addr), None)
            if idx is not None:
                src_line = rows[idx][2]
                lines.append("  where:  %s%s   (%s+0x%x)" % (shown_name, ":%d" % src_line if src_line else "", sym, off))
                for i in range(max(0, idx - 4), min(len(rows), idx + 3)):
                    a, text, ln = rows[i]
                    mark = "  <-- here" if i == idx else ""
                    lines.append("    %s %4x:  %-44s %s%s" % ("=>" if i == idx else "  ", a, text,
                                                              "; line %d" % ln if ln else "", mark))
        else:
            lines.append("  where:  %s+0x%x" % (sym, off))
    elif phase == "candidate":
        lines.append("  where:  pc=%s is outside your code (%s). The stack, x29 or x30 was probably corrupted "
                     "before a `ret`, or you branched through a bad pointer." % (ev.get("pc"), ev.get("pc_symbol") or "unknown"))

    regs = ev.get("regs")
    if regs:
        # Hide registers that still hold what the trampoline put there: only the ones the
        # code actually wrote (plus the arguments) say anything about the bug.
        poison = int(ev.get("poison", "0"), 16)
        garbage = (~poison) & 0xFFFFFFFFFFFFFFFF
        canaries = {(poison + k * 0x111) & 0xFFFFFFFFFFFFFFFF for k in range(10)}
        cells, untouched = [], 0
        for i, r in enumerate(regs):
            v = int(r, 16)
            if i == 18 or (poison and (v == garbage or (19 <= i <= 28 and v in canaries))):
                untouched += i != 18
                continue
            note = _annotate_reg(v, ev)
            name = {29: "x29/fp", 30: "x30/lr"}.get(i, "x%d" % i)
            cells.append("%-6s = %#018x%s" % (name, v, "  " + note if note else ""))
        cells.append("%-6s = %s" % ("sp", ev.get("sp")))
        lines.append("  registers at the fault (%d others still hold the caller's garbage, i.e. your code "
                     "never wrote them):" % untouched)
        for c in cells:
            lines.append("    " + c)
        if "in_ptr" in ev:
            lines.append("  (in = input buffer at %s, len %s%s)" % (
                ev["in_ptr"], ev.get("in_len"),
                "; out = output buffer at %s, capacity %s" % (ev["out_ptr"], ev.get("out_cap")) if "out_ptr" in ev else ""))
    return "\n".join(lines)


ABI_HELP = ("callee-saved registers must hold the same value on return as on entry: x19-x28, x29, sp, and the "
            "low 64 bits of v8-v15 (d8-d15). Save the ones you use on the stack and restore them, or use only "
            "x0-x17 and v0-v7/v16-v31.")


def _fail_report(task: Task, ev: Dict[str, Any], dump: Optional[Path]) -> str:
    lines = []
    kind = ev.get("kind")
    if task.is_bytes:
        lines.append("  input:  case #%s  len=%s  flavor=%s  placement=%s  seed=%s"
                     % (ev.get("case"), ev.get("len"), ev.get("flavor_name"), ev.get("placement"), ev.get("seed")))
    else:
        names = ", ".join("%s=%s" % (n, v) for n, v in zip(task.args, ev.get("args", [])))
        lines.append("  input:  case #%s  %s  (flavor=%s)" % (ev.get("case"), names, ev.get("flavor_name")))
    if kind == "mismatch":
        if ev.get("what") == "output bytes":
            lines.append("  output differs from the reference at byte %s (of %s):" % (ev.get("first_diff_at"), ev.get("out_len")))
            lines.append("    expected[%s..]: %s" % (ev.get("window_from"), ev.get("expected")))
            lines.append("    got     [%s..]: %s" % (ev.get("window_from"), ev.get("got")))
        else:
            what = ev.get("what", "return value")
            try:
                e, g = int(ev.get("expected")), int(ev.get("got"))
                lines.append("  %s: expected %d (%#x), got %d (%#x)" % (what, e, e, g, g))
            except (TypeError, ValueError):
                lines.append("  %s: expected %s, got %s" % (what, ev.get("expected"), ev.get("got")))
    elif kind == "abi":
        lines.append("  the result was right, but these registers were not preserved: %s" % ", ".join(ev.get("clobbered", [])))
        lines.append("  " + ABI_HELP)
    elif kind == "write_out_of_bounds":
        lines.append("  the function wrote outside its output buffer: byte at dst%+d was modified (capacity %s)."
                     % (int(ev.get("offset_from_dst", 0)), ev.get("out_cap")))
    if "input_hex" in ev:
        hx = ev["input_hex"]
        shown = " ".join(hx[i:i + 2] for i in range(0, min(len(hx), 128), 2))
        more = " ..." if len(hx) > 128 or ev.get("input_truncated") else ""
        lines.append("  input bytes (hex): %s%s" % (shown or "(empty)", more))
        try:
            raw = bytes.fromhex(hx[:128])
            lines.append("  input as text:     %r" % raw.decode("latin-1"))
        except ValueError:
            pass
    if dump and dump.exists():
        lines.append("  full input saved to: %s" % dump)
        lines.append("  reproduce:           vibeasm call <file.s> --input %s" % dump)
    return "\n".join(lines)


def flavors(builder: Builder, task: Task) -> List[str]:
    """Names of the task's input flavors (flavor 0 first)."""
    try:
        code, out, _ = run([builder.driver(task), "info"])
    except ToolError:
        return []
    for ev in parse_events(out):
        if ev.get("ev") == "info":
            return list(ev.get("flavors", []))
    return []


def default_dump_dir(builder: Builder, task: Task, source: Path) -> Path:
    """Failing inputs go next to the file inside an agent work directory (the agent can only
    read its own directory), otherwise under the repository's .vibeasm/ scratch area."""
    here = source.resolve().parent
    if (here / ".vibeasm-work.json").is_file():
        return here / ".vibeasm-fail"
    return builder.root / ".vibeasm" / "fail" / task.name


def build_and_lint(builder: Builder, task: Task, source: Path):
    """Returns (candidate, lint_result, failure CheckResult or None)."""
    shown = source.name
    try:
        text = source.read_text(errors="replace")
    except OSError as e:
        return None, None, CheckResult(False, "assemble", "cannot read %s: %s" % (source, e))
    src_errors = lint_source(text, task.forbid_constants)
    try:
        cand = builder.candidate(task, source)
    except BuildError as e:
        return None, None, CheckResult(False, e.stage, "%s does not %s" % (shown, e.stage),
                                       "\n".join("  " + l for l in e.output.splitlines()[:60]))
    lint = lint_object(builder.target, cand.obj, task.symbol, builder.disassemble(cand.obj))
    lint.errors = src_errors + lint.errors
    if not lint.ok:
        return cand, lint, CheckResult(False, "lint", "%s breaks %d rule(s) for solutions" % (shown, len(lint.errors)),
                                       "\n".join("  - " + e for e in lint.errors))
    return cand, lint, None


def check(builder: Builder, task: Task, source: Path, *, seed: int = 1, profile: str = "quick",
          dump_dir: Optional[Path] = None) -> CheckResult:
    cand, lint, failure = build_and_lint(builder, task, source)
    if failure:
        failure.seed, failure.profile = seed, profile
        return failure
    assert cand is not None and lint is not None

    prof = task.fuzz_profile(profile)
    dump = None
    cmd = [str(builder.driver(task)), "check", "--symbol", task.symbol, "--oracle", str(builder.oracle(task)),
           "--cand", "%s=%s" % (source.name, cand.dylib), "--seed", str(seed),
           "--random", str(prof["random"]), "--timeout", str(prof["timeout"])]
    if task.is_bytes:
        cmd += ["--small-max", str(prof["small_max"]), "--max-size", str(prof["max_size"]),
                "--large-size", str(prof["large_size"]), "--sweep-max", str(prof["sweep_max"]),
                "--window-max", str(prof["window_max"]), "--big-windows", str(prof["big_windows"])]
        dump_dir = dump_dir or default_dump_dir(builder, task, source)
        try:
            dump_dir.mkdir(parents=True, exist_ok=True)
            dump = dump_dir / "input.bin"
            if dump.exists():
                dump.unlink()
            cmd += ["--dump", str(dump)]
        except OSError:
            dump = None
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=600, env=clean_env())
    except subprocess.TimeoutExpired:
        return CheckResult(False, "fuzz", "the test run did not finish within 10 minutes", seed=seed, profile=profile)
    events = parse_events(p.stdout)
    info = dict(lint.info)

    crash = next((e for e in events if e.get("ev") == "crash"), None)
    if crash:
        who = "your code" if crash.get("phase") == "candidate" else "the " + str(crash.get("phase"))
        return CheckResult(False, "fuzz", "%s crashed with %s on test case #%s (%s)"
                           % (who, crash.get("signal"), crash.get("case"), crash.get("note", "")),
                           _crash_report(builder, task, cand, crash, source.name) +
                           ("\n  full input saved to: %s\n  reproduce:           vibeasm call <file.s> --input %s" % (dump, dump)
                            if dump and dump.exists() else ""),
                           seed=seed, profile=profile, data={"event": crash, **info})
    fail = next((e for e in events if e.get("ev") == "fail"), None)
    if fail:
        titles = {"mismatch": "wrong result", "abi": "calling-convention violation",
                  "write_out_of_bounds": "wrote outside the output buffer"}
        return CheckResult(False, "fuzz", "%s on test case #%s" % (titles.get(fail.get("kind"), fail.get("kind")), fail.get("case")),
                           _fail_report(task, fail, dump), seed=seed, profile=profile, data={"event": fail, **info})
    done = next((e for e in events if e.get("ev") == "check_done"), None)
    if done and done.get("ok") and p.returncode == 0:
        n = int(done.get("cases", 0))
        return CheckResult(True, "passed",
                           "%s: assembled, lint clean, %d differential test cases passed (%s profile, seed %d); "
                           "%d instructions, %d bytes"
                           % (source.name, n, profile, seed, info.get("instructions", 0), info.get("text_bytes", 0)),
                           cases=n, seed=seed, profile=profile, data=info)
    return CheckResult(False, "internal", "the test driver failed unexpectedly (exit %d)" % p.returncode,
                       "\n".join("  " + l for l in (p.stderr or p.stdout).strip().splitlines()[-20:]),
                       seed=seed, profile=profile)


def call(builder: Builder, task: Task, source: Path, *, input_path: Optional[Path] = None,
         args: Optional[str] = None) -> str:
    """Run one explicit input through the candidate and the reference; returns a short report."""
    cand, _lint, failure = build_and_lint(builder, task, source)
    if failure and failure.stage in ("assemble", "link"):
        return failure.text()
    assert cand is not None
    cmd = [str(builder.driver(task)), "call", "--symbol", task.symbol, "--oracle", str(builder.oracle(task)),
           "--cand", "%s=%s" % (source.name, cand.dylib)]
    if task.is_bytes:
        if not input_path:
            return "this task takes a byte buffer: pass --input FILE, --text STRING or --hex BYTES"
        cmd += ["--input", str(input_path)]
    else:
        if not args:
            return "this task takes integers: pass --args %s" % ",".join(task.args)
        cmd += ["--args", args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=120, env=clean_env())
    except subprocess.TimeoutExpired:
        return "FAIL  the call did not return within 120 s"
    events = parse_events(p.stdout)
    crash = next((e for e in events if e.get("ev") == "crash"), None)
    if crash:
        return "FAIL  crashed with %s (%s)\n%s" % (crash.get("signal"), crash.get("note", ""),
                                                  _crash_report(builder, task, cand, crash, source.name))
    ev = next((e for e in events if e.get("ev") == "call"), None)
    if not ev:
        return "FAIL  the driver produced no result:\n" + (p.stderr or p.stdout).strip()
    lines = []
    if task.shape == "bytes_to_bytes":
        lines.append("%s  output %s the reference" % ("OK  " if ev["match"] else "DIFF", "matches" if ev["match"] else "differs from"))
        lines.append("  reference: %d bytes  %s" % (ev["expected_len"], ev["expected_hex"]))
        lines.append("  yours:     %d bytes  %s" % (ev["got_len"], ev["got_hex"]))
        if not ev["match"] and ev["expected_len"] == ev["got_len"]:
            lines.append("  first difference at output byte %d" % ev["first_diff_at"])
    else:
        e, g = int(ev["expected"]), int(ev["got"])
        lines.append("%s  reference returns %d (%#x), yours returns %d (%#x)"
                     % ("OK  " if ev["match"] else "DIFF", e, e, g, g))
    if ev.get("clobbered"):
        lines.append("  ABI: registers not preserved: %s" % ", ".join(ev["clobbered"]))
    return "\n".join(lines)
