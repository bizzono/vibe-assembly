"""Building: the driver, the oracle, the compiler baseline and assembly candidates.

Everything is cached under .vibeasm/cache/, keyed by the content of its inputs, so
re-checking an unchanged file costs nothing and a changed byte always rebuilds.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from . import __version__
from .target import Target
from .task import Task
from .util import ToolError, must, run, sha256_hex

KIT = Path(__file__).resolve().parent / "kit"


class BuildError(Exception):
    """The candidate did not assemble or link. `output` holds the tool's diagnostics."""

    def __init__(self, stage: str, output: str):
        super().__init__("%s failed" % stage)
        self.stage = stage
        self.output = output


@dataclass
class Candidate:
    source: Path
    obj: Path        # production object (what lint inspects and what gets linked)
    dbg_obj: Path    # same code with line info, for mapping crashes to source lines
    dylib: Path
    key: str


class Builder:
    def __init__(self, root: Path, target: Target):
        self.root = root
        self.target = target
        self.cache = root / ".vibeasm" / "cache"

    # -- helpers ---------------------------------------------------------------
    def _dir(self, kind: str, parts: Sequence[bytes]) -> Path:
        key = sha256_hex([kind.encode(), __version__.encode(), self.target.name.encode()] + list(parts))[:20]
        d = self.cache / ("%s-%s" % (kind, key))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _kit_bytes(self) -> List[bytes]:
        return [(KIT / n).read_bytes() for n in ("driver.c", "va_kit.h", self.target.tramp)]

    # -- task-level artifacts ----------------------------------------------------
    def driver(self, task: Task) -> Path:
        d = self._dir("driver-" + task.name, self._kit_bytes() + [task.gen_path.read_bytes(), task.shape.encode()])
        exe = d / "driver"
        if not exe.exists():
            must([self.target.cc, *self.target.c_flags, "-O2", "-DVA_SHAPE=%d" % task.shape_id, "-I", KIT,
                  KIT / "driver.c", KIT / self.target.tramp, task.gen_path, "-o", exe],
                 what="building the test driver for task '%s' (check gen.c)" % task.name)
        return exe

    def _ref(self, task: Task, kind: str, flags: Sequence[str]) -> Path:
        d = self._dir("%s-%s" % (kind, task.name),
                      [task.ref_path.read_bytes(), " ".join(list(flags) + task.cflags).encode()])
        lib = d / (kind + self.target.dylib_ext)
        if not lib.exists():
            must([self.target.cc, *self.target.c_flags, *flags, *task.cflags, *self.target.shared_flags,
                  task.ref_path, "-o", lib], what="compiling ref.c of task '%s'" % task.name)
        return lib

    def oracle(self, task: Task) -> Path:
        return self._ref(task, "oracle", self.target.oracle_flags)

    def baseline(self, task: Task) -> Path:
        return self._ref(task, "baseline", self.target.baseline_flags)

    def baseline_asm(self, task: Task) -> str:
        """What the optimizing compiler makes of ref.c -- the assembly a solution has to beat."""
        flags = list(self.target.baseline_flags) + task.cflags
        d = self._dir("baseline-asm-" + task.name, [task.ref_path.read_bytes(), " ".join(flags).encode()])
        out = d / "baseline.s"
        if not out.exists():
            must([self.target.cc, *self.target.c_flags, *flags, "-S", "-fno-asynchronous-unwind-tables",
                  task.ref_path, "-o", out], what="compiling ref.c of task '%s'" % task.name)
        return out.read_text()

    def baseline_description(self) -> str:
        return "%s %s" % (self.target.cc, " ".join(self.target.baseline_flags))

    # -- candidates ----------------------------------------------------------------
    def candidate(self, task: Task, source: Path) -> Candidate:
        data = source.read_bytes()
        d = self._dir("cand-" + task.name, [data, source.name.encode(), " ".join(self.target.asm_flags).encode()])
        src = d / "solution.s"
        obj, dbg, lib = d / "cand.o", d / "cand.g.o", d / ("cand" + self.target.dylib_ext)
        fail = d / "build-error.txt"
        if fail.exists():
            stage, _, text = fail.read_text().partition("\n")
            raise BuildError(stage, text)
        if not lib.exists():
            src.write_bytes(data)
            # Assemble under the name the author used so diagnostics point at their file.
            shown = d / source.name if source.suffix == ".s" else src
            if shown != src:
                shown.write_bytes(data)
            code, out, err = run([self.target.cc, *self.target.asm_flags, "-c", shown.name, "-o", obj], cwd=d)
            if code != 0:
                fail.write_text("assemble\n" + (err or out).strip())
                raise BuildError("assemble", (err or out).strip())
            run([self.target.cc, *self.target.asm_flags, "-g", "-c", shown.name, "-o", dbg], cwd=d)
            code, out, err = run([self.target.cc, *self.target.asm_flags, *self.target.shared_flags, obj, "-o", lib])
            if code != 0:
                fail.write_text("link\n" + (err or out).strip())
                raise BuildError("link", (err or out).strip())
        return Candidate(source=source, obj=obj, dbg_obj=dbg, dylib=lib, key=d.name)

    def disassemble(self, obj: Path, with_lines: bool = False) -> str:
        cmd = ["objdump", "-d", "--no-show-raw-insn"]
        if with_lines:
            cmd.append("-l")
        try:
            return must(cmd + [obj], what="objdump")
        except ToolError as e:
            return "(disassembly unavailable: %s)" % e
