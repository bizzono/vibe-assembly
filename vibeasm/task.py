"""Tasks: a spec, a reference implementation and input generators.

    tasks/<name>/
        task.json   machine-readable description (below)
        SPEC.md     the contract, in prose. This is what a human reviews.
        ref.c       reference implementation -- the oracle every candidate is diffed against
        gen.c       input generators (see vibeasm/kit/va_kit.h)

task.json:
    {
      "name": "wordcount",
      "symbol": "wordcount",              C name of the function
      "shape": "bytes_to_u64",            bytes_to_u64 | bytes_to_bytes | ints_to_u64
      "summary": "one line",
      "args": ["width", "height"],        ints_to_u64 only: argument names (1-4)
      "cflags": ["-ffp-contract=off"],    optional extra flags for ref.c
      "goal_speedup": 2.0,                the agent loop stops early once this is reached
      "forbid_constants": [14200],        optional: numbers that may not appear in a solution
                                          (answers a solution must compute, not look up)
      "rivals": [{"name": "zlib", "source": "rivals/zlib.c", "ldflags": ["-lz"], "note": "..."}],
                                          optional: expert implementations to time against
                                          (`vibeasm bench --rivals`); never used as the oracle
      "fuzz": {"small_max": 160, "timeout": 5,
               "quick": {"random": 1500, "max_size": 40000, "large_size": 1500000, "sweep_max": 4300},
               "full":  {"random": 8000, "max_size": 200000, "large_size": 3145741, "sweep_max": 17000}},
                                          (every length up to sweep_max is tested with every flavor)
      "bench": [{"name": "1 KiB", "size": 1024, "flavor": 0}, ...]
               ints_to_u64: [{"name": "n=12", "args": [12]}]
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

SHAPES = {"bytes_to_u64": 1, "bytes_to_bytes": 2, "ints_to_u64": 3}

DEFAULT_FUZZ = {
    "bytes": {
        "quick": {"random": 1500, "max_size": 40000, "large_size": 1500007,
                  "sweep_max": 4300, "window_max": 17000, "big_windows": 0},
        "full": {"random": 8000, "max_size": 200000, "large_size": 3145741,
                 "sweep_max": 17000, "window_max": 140000, "big_windows": 1},
    },
    "ints": {
        "quick": {"random": 400},
        "full": {"random": 3000},
    },
}


class TaskError(Exception):
    pass


@dataclass
class BenchCase:
    name: str
    size: int = 0
    flavor: int = 0
    args: List[int] = field(default_factory=list)
    weight: float = 1.0

    def spec(self, shape: str) -> str:
        if shape == "ints_to_u64":
            return "%s|%s" % (self.name, ",".join(str(a) for a in self.args))
        return "%s|%d|%d" % (self.name, self.size, self.flavor)


@dataclass
class Task:
    name: str
    dir: Path
    symbol: str
    shape: str
    summary: str
    args: List[str]
    cflags: List[str]
    goal_speedup: float
    fuzz: Dict[str, Any]
    bench: List[BenchCase]
    raw: Dict[str, Any]
    forbid_constants: List[int] = field(default_factory=list)
    rivals: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def shape_id(self) -> int:
        return SHAPES[self.shape]

    @property
    def spec_path(self) -> Path:
        return self.dir / "SPEC.md"

    @property
    def ref_path(self) -> Path:
        return self.dir / "ref.c"

    @property
    def gen_path(self) -> Path:
        return self.dir / "gen.c"

    @property
    def is_bytes(self) -> bool:
        return self.shape != "ints_to_u64"

    def signature(self) -> str:
        """The C prototype every implementation of this task has."""
        if self.shape == "bytes_to_u64":
            return "uint64_t %s(const uint8_t *buf, size_t len);" % self.symbol
        if self.shape == "bytes_to_bytes":
            return "size_t %s(const uint8_t *src, size_t len, uint8_t *dst);" % self.symbol
        params = ", ".join("uint64_t %s" % a for a in self.args)
        return "uint64_t %s(%s);" % (self.symbol, params)

    def fuzz_profile(self, profile: str) -> Dict[str, int]:
        base = dict(DEFAULT_FUZZ["bytes" if self.is_bytes else "ints"][profile])
        base.update(self.fuzz.get(profile, {}))
        if self.is_bytes:
            base["small_max"] = int(self.fuzz.get("small_max", 160))
        base["timeout"] = int(self.fuzz.get("timeout", 5))
        return base


def find_root(start: Optional[Path] = None) -> Path:
    """The repository root: nearest ancestor of `start` (or cwd) that has a tasks/ directory,
    falling back to the directory this package lives in."""
    here = (start or Path.cwd()).resolve()
    for d in [here] + list(here.parents):
        if (d / "tasks").is_dir() and (d / "vibeasm").is_dir():
            return d
    return Path(__file__).resolve().parent.parent


def load_task(root: Path, name: str) -> Task:
    d = Path(name)
    if not (d / "task.json").is_file():
        d = root / "tasks" / name
    cfg_path = d / "task.json"
    if not cfg_path.is_file():
        known = ", ".join(list_tasks(root)) or "(none)"
        raise TaskError("no task '%s' (looked for %s). Known tasks: %s" % (name, cfg_path, known))
    try:
        raw = json.loads(cfg_path.read_text())
    except json.JSONDecodeError as e:
        raise TaskError("%s is not valid JSON: %s" % (cfg_path, e))

    shape = raw.get("shape")
    if shape not in SHAPES:
        raise TaskError("%s: \"shape\" must be one of %s" % (cfg_path, ", ".join(SHAPES)))
    symbol = raw.get("symbol") or raw.get("name")
    if not symbol or not str(symbol).replace("_", "a").isalnum():
        raise TaskError("%s: \"symbol\" must be a C identifier" % cfg_path)
    args = list(raw.get("args", []))
    if shape == "ints_to_u64" and not (1 <= len(args) <= 4):
        raise TaskError("%s: ints_to_u64 needs \"args\": 1 to 4 argument names" % cfg_path)

    bench = []
    for b in raw.get("bench", []):
        bench.append(BenchCase(name=str(b["name"]), size=int(b.get("size", 0)), flavor=int(b.get("flavor", 0)),
                               args=[int(a) for a in b.get("args", [])], weight=float(b.get("weight", 1.0))))
    if not bench:
        raise TaskError("%s: \"bench\" needs at least one case" % cfg_path)
    for b in bench:
        if "|" in b.name or '"' in b.name:
            raise TaskError("%s: bench case names may not contain | or \"" % cfg_path)

    for required in ("SPEC.md", "ref.c", "gen.c"):
        if not (d / required).is_file():
            raise TaskError("task '%s' is missing %s" % (raw.get("name", name), d / required))

    return Task(name=str(raw.get("name", d.name)), dir=d.resolve(), symbol=str(symbol), shape=shape,
                summary=str(raw.get("summary", "")), args=args, cflags=list(raw.get("cflags", [])),
                goal_speedup=float(raw.get("goal_speedup", 1.5)), fuzz=dict(raw.get("fuzz", {})),
                bench=bench, raw=raw, forbid_constants=[int(x) for x in raw.get("forbid_constants", [])],
                rivals=list(raw.get("rivals", [])))


def list_tasks(root: Path) -> List[str]:
    tdir = root / "tasks"
    if not tdir.is_dir():
        return []
    return sorted(p.name for p in tdir.iterdir() if (p / "task.json").is_file())
