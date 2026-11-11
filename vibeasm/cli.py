"""Command line: `vibeasm <command>`.

The same commands serve a person at a terminal and an agent inside a work directory.
Inside a work directory (one created by `vibeasm run` or `vibeasm work`) the task is
implied, so the agent types `vibeasm check` and `vibeasm bench v2.s`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Tuple

from . import __version__
from .bench import BenchError, bench, render
from .build import Builder
from .gates import build_and_lint, call, check
from .agent import ClaudeCodeAgent, CommandAgent, ManualAgent, build_brief
from .loop import install, judge, prepare_workdir, provenance, run_task
from .newtask import scaffold
from .target import UnsupportedTarget, describe_host, detect, host_target_name
from .task import Task, TaskError, find_root, list_tasks, load_task
from .util import ToolError, run

WORK_MARKER = ".vibeasm-work.json"  # keep in sync with loop.WORK_MARKER


class UsageError(Exception):
    pass


def work_context(start: Optional[Path] = None) -> Optional[dict]:
    here = (start or Path.cwd()).resolve()
    for d in [here] + list(here.parents)[:2]:
        f = d / WORK_MARKER
        if f.is_file():
            try:
                ctx = json.loads(f.read_text())
                ctx["dir"] = str(d)
                return ctx
            except (json.JSONDecodeError, OSError):
                return None
    return None


class Session:
    """Resolved root, target, builder and (optionally) the work directory we are in."""

    def __init__(self, target_name: str = ""):
        self.ctx = work_context()
        self.root = Path(self.ctx["root"]) if self.ctx else find_root()
        self.target = detect(target_name)
        self.builder = Builder(self.root, self.target)

    def solution_path(self, task: Task) -> Path:
        return self.root / "solutions" / self.target.name / (task.name + ".s")

    def resolve(self, positionals: List[str], many: bool = False) -> Tuple[Task, List[Path]]:
        """Split positionals into (task, files) depending on whether we are in a work directory."""
        pos = list(positionals)
        if self.ctx:
            task = load_task(self.root, self.ctx["task"])
            files = [Path(p) for p in pos] or [Path(self.ctx["dir"]) / "solution.s"]
        else:
            if not pos:
                raise UsageError("which task? Known tasks: %s" % (", ".join(list_tasks(self.root)) or "(none)"))
            task = load_task(self.root, pos[0])
            files = [Path(p) for p in pos[1:]] or [self.solution_path(task)]
        for f in files:
            if not f.is_file():
                raise UsageError("no such file: %s" % f)
        if not many and len(files) > 1:
            raise UsageError("this command takes one file")
        return task, files


# ---- commands ----------------------------------------------------------------------

def cmd_doctor(args) -> int:
    ok = True
    print("vibe-assembly %s" % __version__)
    host = describe_host()
    for k in ("target", "cpu", "os", "cc"):
        print("  %-8s %s" % (k, host.get(k, "?")))
    try:
        target = detect(args.target)
        print("  status   target %s is supported (%s)" % (target.name, target.feature_baseline))
    except UnsupportedTarget as e:
        print("  status   " + str(e).replace("\n", "\n           "))
        return 1
    for tool in (target.cc, "nm", "otool", "objdump"):
        path = shutil.which(tool)
        print("  %-8s %s" % (tool, path or "MISSING"))
        ok = ok and bool(path)
    for agent in ("claude",):
        print("  %-8s %s" % (agent, shutil.which(agent) or "not found (needed only for `vibeasm run --agent claude`)"))
    root = find_root()
    tasks = list_tasks(root)
    print("  tasks    %d in %s" % (len(tasks), root / "tasks"))
    if not ok:
        print("\nMissing tools. On macOS: xcode-select --install")
    return 0 if ok else 1


def cmd_list(args) -> int:
    s = Session(args.target)
    for name in list_tasks(s.root):
        try:
            t = load_task(s.root, name)
        except TaskError as e:
            print("%-18s (broken: %s)" % (name, e))
            continue
        sol = s.solution_path(t)
        meta = sol.with_suffix(".json")
        status = "no solution yet"
        if sol.exists():
            status = "solved"
            if meta.exists():
                try:
                    m = json.loads(meta.read_text())
                    status = "solved, %.2fx vs %s" % (m["score"], m.get("baseline", "baseline"))
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        print("%-18s %-16s %s  [%s]" % (t.name, t.shape, t.summary, status))
    return 0


def cmd_show(args) -> int:
    s = Session(args.target)
    task = load_task(s.root, args.task)
    print("task       %s -- %s" % (task.name, task.summary))
    print("signature  %s" % task.signature())
    print("target     %s (%s)" % (s.target.name, s.target.feature_baseline))
    print("baseline   %s" % s.builder.baseline_description())
    print("spec       %s" % task.spec_path)
    print()
    print(task.spec_path.read_text().rstrip())
    return 0


def cmd_check(args) -> int:
    s = Session(args.target)
    task, files = s.resolve(args.paths)
    res = check(s.builder, task, files[0], seed=args.seed, profile="full" if args.full else "quick")
    if args.json:
        print(json.dumps({"ok": res.ok, "stage": res.stage, "summary": res.summary, "detail": res.detail,
                          "cases": res.cases, "seed": res.seed, "profile": res.profile}))
    else:
        print(res.text())
    return 0 if res.ok else 1


def cmd_bench(args) -> int:
    s = Session(args.target)
    task, files = s.resolve(args.paths, many=True)
    cands: "OrderedDict[str, Path]" = OrderedDict()
    for f in files:
        res = check(s.builder, task, f, seed=args.seed, profile="quick")
        if not res.ok:
            print("%s is not benchmarked because it does not pass `vibeasm check`:\n" % f.name)
            print(res.text())
            return 1
        name = f.stem if f.stem != "baseline" else f.stem + "_"
        while name in cands:
            name += "_"
        cand, _, _ = build_and_lint(s.builder, task, f)
        cands[name] = cand.dylib
    extra = getattr(args, "vs", None) or []
    for v in extra:
        p = Path(v)
        if not p.is_file():
            raise UsageError("no such file: %s" % p)
        cand, _, failure = build_and_lint(s.builder, task, p)
        if failure:
            raise UsageError("--vs %s: %s" % (p, failure.summary))
        cands["vs:" + p.stem] = cand.dylib
    try:
        res = bench(s.builder, task, cands, samples=args.samples, sample_us=args.sample_us)
    except BenchError as e:
        print("FAIL  %s" % e)
        return 1
    if args.json:
        out = res.to_json()
        out["scores"] = {c: res.score(c) for c in res.cands if c != "baseline"}
        print(json.dumps(out))
    else:
        print(render(res, task, s.builder.baseline_description()))
    return 0


def cmd_call(args) -> int:
    s = Session(args.target)
    task, files = s.resolve(args.paths)
    tmp = None
    input_path = Path(args.input) if args.input else None
    if args.text is not None or args.hex is not None:
        data = args.text.encode("utf-8").decode("unicode_escape").encode("latin-1") if args.text is not None \
            else bytes.fromhex(args.hex.replace(" ", ""))
        tmp = tempfile.NamedTemporaryFile(prefix="vibeasm-call-", suffix=".bin", delete=False)
        tmp.write(data)
        tmp.close()
        input_path = Path(tmp.name)
    try:
        out = call(s.builder, task, files[0], input_path=input_path, args=args.args)
    finally:
        if tmp:
            os.unlink(tmp.name)
    print(out)
    return 0 if out.startswith("OK") else 1


def cmd_disasm(args) -> int:
    s = Session(args.target)
    if args.paths and args.paths[-1] == "baseline":
        task, _ = s.resolve(args.paths[:-1]) if (s.ctx or len(args.paths) > 1) else (None, None)
        if task is None:
            raise UsageError("usage: vibeasm disasm <task> baseline")
        print(s.builder.baseline_asm(task).rstrip())
        return 0
    task, files = s.resolve(args.paths)
    cand, _lint, failure = build_and_lint(s.builder, task, files[0])
    if cand is None:
        print(failure.text())
        return 1
    print(s.builder.disassemble(cand.dbg_obj if cand.dbg_obj.exists() else cand.obj, with_lines=args.lines).rstrip())
    return 0


def cmd_baseline(args) -> int:
    s = Session(args.target)
    task = load_task(s.root, s.ctx["task"]) if s.ctx and not args.task else load_task(s.root, args.task or "")
    print("// %s on %s" % (s.builder.baseline_description(), task.ref_path.name))
    print(s.builder.baseline_asm(task).rstrip())
    return 0


def cmd_cpu(args) -> int:
    host = describe_host()
    target = detect(args.target)
    print("cpu      %s" % host.get("cpu", "?"))
    print("target   %s" % target.name)
    print("assume   %s" % target.feature_baseline)
    if sys.platform == "darwin":
        code, out, _ = run(["sysctl", "-a"])
        feats = sorted(l.split(":")[0].split("FEAT_")[1] for l in out.splitlines()
                       if l.startswith("hw.optional.arm.FEAT_") and l.strip().endswith(": 1"))
        print("this cpu %s" % " ".join(feats))
        print("\nSolutions are assembled for the `assume` line, not for this CPU, so they run on every "
              "Apple Silicon Mac.")
    return 0


SANDBOX_COMMANDS = {"check", "bench", "call", "disasm", "baseline", "cpu", "show", "list"}


def make_agent(args):
    if args.agent == "claude":
        return ClaudeCodeAgent(model=args.model, effort=args.effort, max_budget_usd=args.budget,
                               timeout_s=args.timeout * 60)
    if args.agent == "cmd":
        return CommandAgent(args.agent_cmd or "", agentic=args.agentic, timeout_s=args.timeout * 60)
    if args.agent == "manual":
        return ManualAgent()
    raise UsageError("unknown agent '%s' (claude, cmd, manual)" % args.agent)


def cmd_run(args) -> int:
    s = Session(args.target)
    names = list_tasks(s.root) if args.task == "all" else [args.task]
    agent = make_agent(args)
    problem = agent.available()
    if problem:
        raise UsageError(problem)
    worst = 0
    for name in names:
        task = load_task(s.root, name)
        res = run_task(s.builder, task, agent, rounds=args.rounds, fresh=args.fresh,
                       do_install=not args.no_install, stop_at_goal=not args.all_rounds)
        if not res.ok:
            print("\n%s: %s (run directory: %s)" % (task.name, res.message, res.run_dir))
            worst = 1
        else:
            print("\n%s: best verified solution scores %.2fx (run directory: %s)" % (task.name, res.score, res.run_dir))
    return worst


def cmd_brief(args) -> int:
    s = Session(args.target)
    task = load_task(s.root, args.task)
    print(build_brief(s.builder, task, agentic=not args.oneshot))
    return 0


def cmd_work(args) -> int:
    s = Session(args.target)
    task = load_task(s.root, args.task)
    work = Path(args.dir) if args.dir else s.root / "runs" / task.name / "manual" / "work"
    current = s.solution_path(task)
    prepare_workdir(s.builder, task, work, agentic=True, seed_solution=current if current.exists() else None,
                    best=current if current.exists() else None)
    print("work directory: %s" % work)
    print("  TASK.md      the brief            ABI.md       registers, syntax, traps")
    print("  ref.c        the reference        baseline.s   what the compiler produces")
    print("  solution.s   write your assembly here")
    print("\ncd there, then: vibeasm check | vibeasm bench | vibeasm call --text '...'")
    print("when it is good: vibeasm accept %s %s" % (task.name, work / "solution.s"))
    return 0


def cmd_accept(args) -> int:
    s = Session(args.target)
    task = load_task(s.root, args.task)
    source = Path(args.file)
    if not source.is_file():
        raise UsageError("no such file: %s" % source)
    current = s.solution_path(task)
    vs = {"installed": current} if current.exists() and current.resolve() != source.resolve() else None
    print("verifying %s with fresh seeds (full profile)..." % source)
    v = judge(s.builder, task, source, vs=vs, samples=101)
    if not v.ok:
        print(v.check.text())
        return 1
    print(v.bench_text)
    if vs and v.bench is not None and "installed" in v.bench.cands and not args.force:
        old = v.bench.score("installed")
        if v.score <= old * 1.02:
            print("\nnot installed: the installed solution scores %.2fx and this one %.2fx. "
                  "Use --force to replace it anyway." % (old, v.score))
            return 1
    record = provenance(s.builder, task, source, v, agent={"backend": args.by or "manual", "model": args.model or "",
                                                          "rounds": 0, "cost_usd": 0, "turns": 0, "minutes": 0})
    dest = install(s.builder, task, source, record)
    print("\ninstalled %s  (%.2fx vs the compiler, %d hold-out test cases)" % (dest.relative_to(s.root), v.score, v.cases))
    return 0


def cmd_verify(args) -> int:
    s = Session(args.target)
    names = args.tasks or list_tasks(s.root)
    failed = 0
    for name in names:
        task = load_task(s.root, name)
        sol = s.solution_path(task)
        if not sol.exists():
            print("%-16s no solution for %s" % (task.name, s.target.name))
            continue
        if args.quick:
            res = check(s.builder, task, sol, seed=args.seed or 1, profile="quick")
            print("%-16s %s" % (task.name, "PASS  %d cases" % res.cases if res.ok else "FAIL  " + res.summary))
            failed += not res.ok
            continue
        v = judge(s.builder, task, sol, samples=args.samples)
        print("%-16s %s" % (task.name, v.summary()))
        if not v.ok:
            print(v.check.text())
            failed += 1
            continue
        if args.verbose:
            print(v.bench_text + "\n")
        meta = sol.with_suffix(".json")
        if args.update:
            agent = {"backend": "unknown"}
            if meta.exists():
                try:
                    agent = json.loads(meta.read_text()).get("agent", agent)
                except json.JSONDecodeError:
                    pass
            meta.write_text(json.dumps(provenance(s.builder, task, sol, v, agent=agent), indent=2) + "\n")
    return 1 if failed else 0


def cmd_new(args) -> int:
    s = Session(args.target)
    d = scaffold(s.root, args.name, args.shape, [a for a in (args.args or "").split(",") if a])
    print("created %s" % d)
    print("  SPEC.md    write the contract            ref.c   write the reference (the oracle)")
    print("  gen.c      describe test inputs          task.json   benchmark cases, goal")
    print("\nthen: vibeasm run %s      (or: vibeasm work %s)" % (args.name, args.name))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vibeasm", description="An agent harness for writing verified, benchmarked assembly.")
    p.add_argument("--version", action="version", version="vibe-assembly " + __version__)
    p.add_argument("--target", default="", help="target to build for (default: this machine: %s)" % host_target_name())
    sub = p.add_subparsers(dest="command", metavar="<command>")

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("doctor", cmd_doctor, "check that the toolchain this harness needs is installed")
    add("list", cmd_list, "list tasks and whether they have a solution")
    sp = add("show", cmd_show, "print a task's contract")
    sp.add_argument("task")

    sp = add("check", cmd_check, "assemble, lint and differentially fuzz a solution against the reference")
    sp.add_argument("paths", nargs="*", metavar="[task] [file.s]")
    sp.add_argument("--full", action="store_true", help="the long fuzz profile the harness uses to accept a solution")
    sp.add_argument("--seed", type=int, default=1)
    sp.add_argument("--json", action="store_true")

    sp = add("bench", cmd_bench, "time one or more solutions against the compiler baseline")
    sp.add_argument("paths", nargs="*", metavar="[task] [file.s ...]")
    sp.add_argument("--vs", action="append", help="also time this already-verified file (repeatable)")
    sp.add_argument("--samples", type=int, default=41)
    sp.add_argument("--sample-us", type=int, default=400)
    sp.add_argument("--seed", type=int, default=1)
    sp.add_argument("--json", action="store_true")

    sp = add("call", cmd_call, "run the solution and the reference on one input you choose")
    sp.add_argument("paths", nargs="*", metavar="[task] [file.s]")
    sp.add_argument("--input", help="file holding the input bytes")
    sp.add_argument("--text", help="input bytes as a string (C escapes like \\n \\x00 allowed)")
    sp.add_argument("--hex", help="input bytes in hex")
    sp.add_argument("--args", help="integer arguments, comma separated (ints_to_u64 tasks)")

    sp = add("disasm", cmd_disasm, "disassemble a solution (or `baseline`: the compiler's assembly for ref.c)")
    sp.add_argument("paths", nargs="*", metavar="[task] [file.s|baseline]")
    sp.add_argument("--lines", action="store_true", help="interleave source line numbers")

    sp = add("baseline", cmd_baseline, "print the assembly the optimizing compiler produces for ref.c")
    sp.add_argument("task", nargs="?")

    add("cpu", cmd_cpu, "show the CPU features a solution may assume")

    sp = add("run", cmd_run, "have an agent write (or improve) the solution for a task, verifying every round")
    sp.add_argument("task", help="task name, or `all`")
    sp.add_argument("--agent", default="claude", help="claude (Claude Code, headless) | cmd | manual")
    sp.add_argument("--agent-cmd", help="for --agent cmd: shell command; the brief is on stdin, {brief} and {workdir} are substituted")
    sp.add_argument("--agentic", action="store_true", help="for --agent cmd: the command can run `vibeasm` itself and edits solution.s")
    sp.add_argument("--model", default="", help="model for the agent (default: the agent's own default)")
    sp.add_argument("--effort", default="", help="reasoning effort for the agent, if it has such a setting")
    sp.add_argument("--rounds", type=int, default=3, help="maximum rounds (default 3)")
    sp.add_argument("--all-rounds", action="store_true", help="do not stop early when the task's goal is reached")
    sp.add_argument("--budget", type=float, default=0.0, help="spending cap per round in USD, if the agent supports one")
    sp.add_argument("--timeout", type=int, default=60, help="minutes per round (default 60)")
    sp.add_argument("--fresh", action="store_true", help="ignore the installed solution instead of trying to beat it")
    sp.add_argument("--no-install", action="store_true", help="do not write the winner to solutions/")

    sp = add("brief", cmd_brief, "print the brief an agent gets for a task (paste it into any chat model)")
    sp.add_argument("task")
    sp.add_argument("--oneshot", action="store_true", help="the version for a model that cannot run tools")

    sp = add("work", cmd_work, "create a work directory to write a solution by hand or in an interactive agent session")
    sp.add_argument("task")
    sp.add_argument("dir", nargs="?")

    sp = add("accept", cmd_accept, "fully verify a file and install it as the task's solution")
    sp.add_argument("task")
    sp.add_argument("file")
    sp.add_argument("--force", action="store_true", help="install even if it is not faster than the current solution")
    sp.add_argument("--by", help="who wrote it, for the provenance record (e.g. 'claude-code interactive')")
    sp.add_argument("--model", help="model name, for the provenance record")

    sp = add("verify", cmd_verify, "re-verify and re-time the installed solutions")
    sp.add_argument("tasks", nargs="*")
    sp.add_argument("--quick", action="store_true", help="quick fuzz profile, no timing")
    sp.add_argument("--update", action="store_true", help="rewrite the provenance records with fresh numbers")
    sp.add_argument("--samples", type=int, default=61)
    sp.add_argument("--seed", type=int, default=0)
    sp.add_argument("-v", "--verbose", action="store_true")

    sp = add("new", cmd_new, "scaffold a new task")
    sp.add_argument("name")
    sp.add_argument("--shape", default="bytes_to_u64", help="bytes_to_u64 | bytes_to_bytes | ints_to_u64")
    sp.add_argument("--args", help="ints_to_u64: comma-separated argument names")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 2
    if os.environ.get("VIBEASM_SANDBOX") and args.command not in SANDBOX_COMMANDS:
        print("vibeasm: `%s` is not available inside an agent session (allowed: %s)"
              % (args.command, ", ".join(sorted(SANDBOX_COMMANDS))), file=sys.stderr)
        return 2
    try:
        return int(args.fn(args) or 0)
    except (UsageError, TaskError, UnsupportedTarget) as e:
        print("vibeasm: %s" % e, file=sys.stderr)
        return 2
    except ToolError as e:
        print("vibeasm: %s\n%s" % (e, e.output), file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130
