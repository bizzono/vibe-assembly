"""Timing: candidates against the compiler baseline, in one process, interleaved.

The number that matters is the *minimum* time per call over many samples: on a machine
that is doing other things, noise only ever adds time, so the minimum is the best
estimate of what the code costs. Each timed call's result is also checked against the
oracle, so a candidate cannot be fast by being wrong.
"""
from __future__ import annotations

import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .build import Builder
from .gates import parse_events
from .task import Task
from .util import clean_env, fmt_ns, fmt_rate, geomean, table


class BenchError(Exception):
    pass


@dataclass
class BenchResult:
    task: str
    cases: List[str]
    cands: List[str]
    rows: Dict[Tuple[str, str], Dict] = field(default_factory=dict)   # (cand, case) -> event

    def min_ns(self, cand: str, case: str) -> float:
        return float(self.rows[(cand, case)]["min_ns"])

    def speedups(self, cand: str, base: str = "baseline") -> List[float]:
        return [self.min_ns(base, c) / self.min_ns(cand, c) for c in self.cases]

    def score(self, cand: str, base: str = "baseline") -> float:
        """Geometric mean speed-up over the task's benchmark cases (>1 means faster than base)."""
        return geomean(self.speedups(cand, base))

    def noise(self) -> float:
        """Worst (median/min - 1) seen: how unsettled the machine was."""
        worst = 0.0
        for ev in self.rows.values():
            if ev["min_ns"] > 0:
                worst = max(worst, ev["median_ns"] / ev["min_ns"] - 1.0)
        return worst

    def to_json(self) -> Dict:
        return {"task": self.task, "cases": self.cases, "cands": self.cands,
                "rows": [{"cand": k[0], "case": k[1], **{f: v[f] for f in ("size", "min_ns", "median_ns", "mean_ns", "samples", "inner")}}
                         for k, v in self.rows.items()]}


def bench(builder: Builder, task: Task, cands: "OrderedDict[str, Path]", *, samples: int = 41,
          sample_us: int = 400, seed: int = 7) -> BenchResult:
    """Time `cands` (name -> shared library). The compiler baseline is always included first."""
    libs: "OrderedDict[str, Path]" = OrderedDict()
    libs["baseline"] = builder.baseline(task)
    for name, lib in cands.items():
        if name == "baseline":
            raise BenchError("'baseline' is reserved for the compiler baseline")
        libs[name] = lib
    cmd = [str(builder.driver(task)), "bench", "--symbol", task.symbol, "--oracle", str(builder.oracle(task)),
           "--samples", str(samples), "--sample-us", str(sample_us), "--seed", str(seed)]
    for name, lib in libs.items():
        cmd += ["--cand", "%s=%s" % (name, lib)]
    for bc in task.bench:
        cmd += ["--case", bc.spec(task.shape)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=900, env=clean_env())
    except subprocess.TimeoutExpired:
        raise BenchError("benchmark did not finish within 15 minutes")
    events = parse_events(p.stdout)
    crash = next((e for e in events if e.get("ev") == "crash"), None)
    if crash:
        raise BenchError("'%s' crashed with %s while being timed on case %s (%s)"
                         % (crash.get("cand"), crash.get("signal"), crash.get("case"), crash.get("note", "")))
    res = BenchResult(task=task.name, cases=[b.name for b in task.bench], cands=list(libs))
    for ev in events:
        if ev.get("ev") == "bench":
            res.rows[(ev["cand"], ev["case"])] = ev
            if not ev.get("correct", False):
                raise BenchError("'%s' returned a wrong result while being timed on case '%s'"
                                 % (ev["cand"], ev["case"]))
    missing = [(c, k) for c in res.cands for k in res.cases if (c, k) not in res.rows]
    if missing or p.returncode != 0:
        raise BenchError("benchmark driver failed (exit %d): %s" % (p.returncode, (p.stderr or p.stdout).strip()[-400:]))
    return res


def render(res: BenchResult, task: Task, baseline_desc: str, highlight: Optional[str] = None) -> str:
    others = [c for c in res.cands if c != "baseline"]
    head = ["case", "baseline"] + [x for c in others for x in (c, "vs baseline")]
    rows = [head]
    for bc in task.bench:
        b = res.min_ns("baseline", bc.name)
        row = [bc.name, _cell(b, bc.size if task.is_bytes else 0)]
        for c in others:
            t = res.min_ns(c, bc.name)
            row += [_cell(t, bc.size if task.is_bytes else 0), "%.2fx" % (b / t)]
        rows.append(row)
    row = ["geomean", ""]
    for c in others:
        row += ["", "%.2fx" % res.score(c)]
    rows.append(row)
    out = [table(rows, "l" + "r" * (len(head) - 1))]
    out.append("")
    out.append("baseline = %s on ref.c. Times are the minimum per call over %d samples; every timed "
               "call was checked against the reference." % (baseline_desc, next(iter(res.rows.values()))["samples"]))
    out.append(">1.00x means faster than the compiler.")
    n = res.noise()
    if n > 0.15:
        out.append("note: the machine was busy (median up to %.0f%% above minimum); differences under ~5%% are noise."
                   % (n * 100))
    return "\n".join(out)


def _cell(ns: float, size: int) -> str:
    rate = fmt_rate(size, ns) if size else ""
    return "%s%s" % (fmt_ns(ns), "  %s" % rate if rate else "")
