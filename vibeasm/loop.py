"""The round loop: brief the agent, take back a file, believe nothing, verify everything.

    for each round:
        write the brief (with the harness's verdict on the previous round)
        let the agent work in the work directory
        take solution.s, re-verify it with seeds the agent never saw, time it
        keep it if it is the fastest verified file so far
    install the winner in solutions/<target>/<task>.s with a provenance record

The agent's own claims ("passes", "6x faster") are never used. Only files are.
"""
from __future__ import annotations

import datetime
import json
import secrets
import shutil
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import __version__
from .agent import AgentResult, build_brief, starter
from .bench import BenchError, BenchResult, bench, render
from .build import Builder
from .gates import CheckResult, build_and_lint, check
from .target import describe_host
from .task import Task
from .util import file_sha256

WORK_MARKER = ".vibeasm-work.json"
IMPROVEMENT = 1.02   # a new file must score 2% higher to replace the current best (timing noise)


@dataclass
class Verdict:
    """The harness's independent judgement of one file."""
    ok: bool
    check: CheckResult
    score: float = 0.0
    bench: Optional[BenchResult] = None
    bench_text: str = ""
    seeds: List[int] = field(default_factory=list)
    cases: int = 0
    error: str = ""

    def summary(self) -> str:
        if not self.ok:
            return "REJECTED (%s): %s" % (self.check.stage, self.error or self.check.summary)
        return "VERIFIED, %.2fx vs the compiler (%d hold-out test cases)" % (self.score, self.cases)


def judge(builder: Builder, task: Task, source: Path, *, vs: Optional[Dict[str, Path]] = None,
          samples: int = 61, dump_dir: Optional[Path] = None, seeds: int = 2) -> Verdict:
    """Full verification with fresh random seeds, then a benchmark. Nothing here is visible
    to the agent beforehand."""
    used, total, last = [], 0, None
    for _ in range(seeds):
        seed = secrets.randbits(31) + 2
        last = check(builder, task, source, seed=seed, profile="full", dump_dir=dump_dir)
        used.append(seed)
        if not last.ok:
            return Verdict(False, last, seeds=used)
        total += last.cases
    assert last is not None
    cand, _lint, _fail = build_and_lint(builder, task, source)
    cands: "OrderedDict[str, Path]" = OrderedDict()
    cands["solution"] = cand.dylib
    for name, path in (vs or {}).items():
        other, _l, failure = build_and_lint(builder, task, path)
        if other is not None and failure is None:
            cands[name] = other.dylib
    try:
        res = bench(builder, task, cands, samples=samples, sample_us=500)
    except BenchError as e:
        bad = CheckResult(False, "bench", str(e))
        return Verdict(False, bad, seeds=used, cases=total, error=str(e))
    return Verdict(True, last, score=res.score("solution"), bench=res,
                   bench_text=render(res, task, builder.baseline_description()), seeds=used, cases=total)


def prepare_workdir(builder: Builder, task: Task, work: Path, *, agentic: bool = True, feedback: str = "",
                    best: Optional[Path] = None, best_score: Optional[float] = None,
                    seed_solution: Optional[Path] = None) -> None:
    """Create or refresh a work directory: everything an agent needs, nothing it could break."""
    work.mkdir(parents=True, exist_ok=True)
    (work / WORK_MARKER).write_text(json.dumps({"task": task.name, "root": str(builder.root),
                                                "target": builder.target.name}, indent=1))
    (work / "SPEC.md").write_text(task.spec_path.read_text())
    (work / "ref.c").write_text(task.ref_path.read_text())
    (work / "baseline.s").write_text("// %s on ref.c -- the assembly you have to beat\n%s"
                                     % (builder.baseline_description(), builder.baseline_asm(task)))
    (work / "ABI.md").write_text((Path(__file__).resolve().parent / "prompts" / builder.target.abi_sheet).read_text())
    if best is not None:
        shutil.copyfile(best, work / "best.s")
    sol = work / "solution.s"
    if not sol.exists():
        if seed_solution is not None:
            shutil.copyfile(seed_solution, sol)
        else:
            sol.write_text(starter(builder, task))
    notes = work / "NOTES.md"
    if not notes.exists():
        notes.write_text("# Lab notebook: %s\n\nWhat was tried, what it measured, what to try next.\n" % task.name)
    (work / "TASK.md").write_text(build_brief(builder, task, agentic=agentic, feedback=feedback,
                                              best_score=best_score))


def provenance(builder: Builder, task: Task, source: Path, verdict: Verdict, *, agent: Dict[str, Any]) -> Dict[str, Any]:
    assert verdict.bench is not None
    res = verdict.bench
    cases = []
    for bc in task.bench:
        b, s = res.min_ns("baseline", bc.name), res.min_ns("solution", bc.name)
        entry = {"name": bc.name, "baseline_ns": round(b, 3), "solution_ns": round(s, 3), "speedup": round(b / s, 3)}
        if task.is_bytes:
            entry["bytes"] = bc.size
        cases.append(entry)
    return {
        "task": task.name,
        "symbol": task.symbol,
        "target": builder.target.name,
        "score": round(verdict.score, 3),
        "score_is": "geometric mean speed-up over the benchmark cases; baseline = 1.0",
        "baseline": builder.baseline_description() + " on ref.c",
        "cases": cases,
        "verified": {"profile": "full", "test_cases": verdict.cases, "seeds": verdict.seeds,
                     "instructions": verdict.check.data.get("instructions"),
                     "text_bytes": verdict.check.data.get("text_bytes")},
        "sha256": file_sha256(source),
        "agent": agent,
        "harness": "vibe-assembly " + __version__,
        "host": describe_host(),
        "date": datetime.date.today().isoformat(),
    }


def install(builder: Builder, task: Task, source: Path, record: Dict[str, Any]) -> Path:
    dest = builder.root / "solutions" / builder.target.name / (task.name + ".s")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    dest.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
    return dest


@dataclass
class RunResult:
    ok: bool
    run_dir: Path
    best: Optional[Path] = None
    score: float = 0.0
    rounds: List[Dict[str, Any]] = field(default_factory=list)
    installed: Optional[Path] = None
    message: str = ""


def latest_run_dir(builder: Builder, task: Task) -> Optional[Path]:
    base = builder.root / "runs" / task.name
    runs = sorted(d for d in base.iterdir() if (d / "work").is_dir()) if base.is_dir() else []
    return runs[-1] if runs else None


def run_task(builder: Builder, task: Task, agent, *, rounds: int = 3, fresh: bool = False,
             do_install: bool = True, say: Callable[[str], None] = print, run_dir: Optional[Path] = None,
             stop_at_goal: bool = True, resume: bool = False) -> RunResult:
    """Up to `rounds` agent rounds. With `resume`, continue the most recent run of this task
    in its existing work directory (the agent's notes and variants are still there)."""
    history: List[Dict[str, Any]] = []
    totals = {"cost_usd": 0.0, "turns": 0, "seconds": 0.0}
    if resume and run_dir is None:
        run_dir = latest_run_dir(builder, task)
        if run_dir is None:
            say("nothing to resume for %s; starting a new run" % task.name)
            resume = False
    if resume and run_dir is not None and (run_dir / "run.json").exists():
        try:
            old = json.loads((run_dir / "run.json").read_text())
            history = list(old.get("rounds", []))
            totals.update(old.get("totals", {}))
        except json.JSONDecodeError:
            pass
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = run_dir or (builder.root / "runs" / task.name / stamp)
    work = run_dir / "work"
    run_dir.mkdir(parents=True, exist_ok=True)
    agentic = bool(getattr(agent, "agentic", False))

    best_path: Optional[Path] = None
    best_score = 0.0
    feedback = ""
    model_used = ""
    seed_solution = None

    def save() -> None:
        (run_dir / "run.json").write_text(json.dumps({"task": task.name, "rounds": history, "totals": totals}, indent=2))

    def rejection(v: Verdict, what: str) -> str:
        return ("%s was **rejected** by the harness's hold-out verification (inputs you had not seen). "
                "It is still in `solution.s`. Fix this first:\n\n```\n%s\n```\n\n%s"
                % (what, v.check.text(), "The best verified file so far is `best.s` (%.2fx)." % best_score
                   if best_path else "There is no verified solution yet."))

    say("task %s  target %s  agent %s  rounds %d  goal %gx" % (task.name, builder.target.name, agent.name, rounds, task.goal_speedup))
    current = builder.root / "solutions" / builder.target.name / (task.name + ".s")
    if resume and (work / "solution.s").exists():
        say("resuming %s: judging the solution.s left in the work directory..." % run_dir.name)
        v = judge(builder, task, work / "solution.s", dump_dir=work / ".vibeasm-fail")
        say("  " + v.summary())
        if v.ok:
            best_path = run_dir / "best.s"
            shutil.copyfile(work / "solution.s", best_path)
            best_score = v.score
            feedback = ("`solution.s` verifies and scores %.2fx (goal: %gx).\n\n```\n%s\n```"
                        % (v.score, task.goal_speedup, v.bench_text))
        else:
            feedback = rejection(v, "The `solution.s` from the previous session")
    elif current.exists() and not fresh:
        # Start from the installed solution, if it still verifies.
        say("re-verifying the installed solution to use as the mark to beat...")
        v = judge(builder, task, current, dump_dir=run_dir / "fail")
        if v.ok:
            best_path = run_dir / "best.s"
            shutil.copyfile(current, best_path)
            best_score = v.score
            seed_solution = current
            feedback = ("A verified solution already exists and scores %.2fx. It is in `best.s` and is the starting "
                        "content of `solution.s`. Your job is to beat it.\n\n```\n%s\n```" % (v.score, v.bench_text))
            say("  installed solution: %s" % v.summary())
        else:
            say("  installed solution no longer verifies (%s); starting fresh" % v.check.summary)

    result = RunResult(ok=False, run_dir=run_dir, rounds=history)
    first, last = len(history) + 1, len(history) + rounds
    r = first
    finalized = False
    while not finalized:
        want_round = r <= last and not (stop_at_goal and best_path and best_score >= task.goal_speedup and r > first)
        if resume and r == first and best_path and best_score >= task.goal_speedup and stop_at_goal:
            want_round = False
        if want_round:
            rdir = run_dir / "rounds" / ("%02d" % r)
            rdir.mkdir(parents=True, exist_ok=True)
            prepare_workdir(builder, task, work, agentic=agentic, feedback=feedback, best=best_path,
                            best_score=best_score or None, seed_solution=seed_solution)
            shutil.copyfile(work / "TASK.md", rdir / "brief.md")
            say("\nround %d/%d: agent working in %s" % (r, last, work))
            t0 = time.time()
            ares: AgentResult = agent.run(work, builder.root, rdir / "agent.log", on_event=say)
            totals["cost_usd"] += ares.cost_usd
            totals["turns"] += ares.turns
            totals["seconds"] += ares.seconds or (time.time() - t0)
            model_used = ares.model or model_used
            (rdir / "agent-final.md").write_text(ares.message or ares.error or "")
            entry: Dict[str, Any] = {"round": r, "agent_ok": ares.ok, "agent_error": ares.error,
                                     "cost_usd": round(ares.cost_usd, 4), "turns": ares.turns,
                                     "seconds": round(ares.seconds, 1)}
            history.append(entry)
            r += 1
            sol = work / "solution.s"
            if not sol.exists():
                entry.update(verified=False, verdict="no solution.s was produced")
                feedback = "The previous round produced no `solution.s`."
                say("  no solution.s produced%s" % (": " + ares.error if ares.error else ""))
                save()
                if not ares.ok and "not found" in ares.error:
                    break
                continue
            snap = rdir / "solution.s"
            shutil.copyfile(sol, snap)

            say("  judging with hold-out seeds...")
            vs = {"previous_best": best_path} if best_path else None
            v = judge(builder, task, snap, vs=vs, dump_dir=work / ".vibeasm-fail")
            entry.update(verified=v.ok, verdict=v.summary(), score=round(v.score, 3), seeds=v.seeds, test_cases=v.cases)
            (rdir / "verdict.txt").write_text(v.summary() + "\n\n" + (v.bench_text if v.ok else v.check.text()) + "\n")
            say("  " + v.summary())
            note = ["", "## Round %d -- harness verdict" % (r - 1), ""]
            if v.ok:
                improved = v.score > best_score * IMPROVEMENT
                if improved:
                    best_path = run_dir / "best.s"
                    shutil.copyfile(snap, best_path)
                    best_score = v.score
                entry["new_best"] = improved
                note += ["Verified on hold-out seeds. Score **%.2fx**%s." % (
                    v.score, " (new best)" if improved else " (not better than the best so far, %.2fx)" % best_score),
                    "", "```", v.bench_text, "```"]
                slowest = min(zip(v.bench.speedups("solution"), [b.name for b in task.bench]))
                feedback = ("The previous round's `solution.s` was **verified** on hold-out seeds and scores %.2fx "
                            "(best so far: %.2fx, in `best.s`; goal: %gx).\n\n```\n%s\n```\n\n"
                            "The weakest case is `%s` at %.2fx. Read `NOTES.md` for what has been tried, then look for "
                            "what is left: a different algorithm, not just polish."
                            % (v.score, best_score, task.goal_speedup, v.bench_text, slowest[1], slowest[0]))
            else:
                note += ["**Rejected** by the hold-out verification:", "", "```", v.check.text(), "```"]
                feedback = rejection(v, "The previous round's `solution.s`")
            with open(work / "NOTES.md", "a") as f:
                f.write("\n".join(note) + "\n")
            save()
            continue

        # No more rounds wanted: the winner has to survive one more, independent verification.
        if best_path is None:
            break
        if not do_install:
            finalized = True
            break
        say("\nfinal verification of the winner (new seeds) before installing...")
        v = judge(builder, task, best_path, samples=101, dump_dir=work / ".vibeasm-fail")
        if v.ok:
            record = provenance(builder, task, best_path, v, agent={
                "backend": agent.name, "model": model_used, "rounds": len(history),
                "cost_usd": round(totals["cost_usd"], 2), "turns": totals["turns"],
                "minutes": round(totals["seconds"] / 60.0, 1)})
            result.installed = install(builder, task, best_path, record)
            best_score = v.score
            say(v.bench_text)
            say("\ninstalled %s  (%.2fx vs the compiler)" % (result.installed.relative_to(builder.root), v.score))
            finalized = True
            break
        # It verified before and fails now: a rare bug. Never install it; send it back.
        say("  " + v.summary())
        history.append({"round": "final", "verified": False, "verdict": v.summary(), "seeds": v.seeds})
        with open(work / "NOTES.md", "a") as f:
            f.write("\n## Final verification -- REJECTED\n\nThe file that had verified earlier failed on new seeds:\n\n```\n%s\n```\n"
                    % v.check.text())
        shutil.copyfile(best_path, work / "solution.s")
        best_path, best_score = None, 0.0
        feedback = rejection(v, "Your solution passed one hold-out verification and then **failed the next one**: "
                                "it has a bug that only rare inputs reach. That file")
        save()
        if r > last:
            result.message = "the best candidate failed final verification: " + v.check.summary
            break

    save()
    result.best, result.score = best_path, best_score
    result.ok = best_path is not None and (finalized or not do_install)
    if best_path is None and not result.message:
        result.message = "no verified solution after %d round(s)" % len(history)
    return result
