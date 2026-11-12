"""Tests of the harness itself.

The harness's whole job is to refuse wrong assembly, so most of these tests feed it
assembly that is wrong in one specific way and assert that the right gate says so.

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vibeasm.agent import CommandAgent, build_brief, extract_code_block  # noqa: E402
from vibeasm.build import Builder  # noqa: E402
from vibeasm.gates import check  # noqa: E402
from vibeasm.lint import lint_source  # noqa: E402
from vibeasm.loop import judge, run_task  # noqa: E402
from vibeasm.newtask import scaffold  # noqa: E402
from vibeasm.target import UnsupportedTarget, detect  # noqa: E402
from vibeasm.task import list_tasks, load_task  # noqa: E402

try:
    TARGET = detect()
except UnsupportedTarget:
    TARGET = None

ZOO = ROOT / "tests" / "zoo" / "wordcount"

# file -> (gate that must reject it, text that must appear in the report)
EXPECT = {
    "ok_scalar.s": ("passed", "differential test cases passed"),
    "bad_syntax.s": ("assemble", "unrecognized instruction"),
    "bad_wrong_symbol.s": ("lint", "does not export _wordcount"),
    "bad_extra_export.s": ("lint", "_helper"),
    "bad_extern.s": ("lint", "_strlen"),
    "bad_data_section.s": ("lint", "writable data"),
    "bad_syscall.s": ("lint", "system call"),
    "bad_x18.s": ("lint", "x18"),
    "bad_arch_directive.s": ("lint", ".arch"),
    "bad_wrong_result.s": ("fuzz", "wrong result"),
    "bad_uninit_register.s": ("fuzz", "wrong result"),
    "bad_overflow_large.s": ("fuzz", "wrong result"),
    "bad_real_lane_overflow.s": ("fuzz", "len=16177"),      # the agent's own bug, see the file
    "bad_overread.s": ("fuzz", "PAST THE END of the input buffer"),
    "bad_underread.s": ("fuzz", "BEFORE THE START of the input buffer"),
    "bad_writes_input.s": ("fuzz", "read-only INPUT buffer"),
    "bad_clobber_x19.s": ("fuzz", "not preserved: x19"),
    "bad_clobber_d8.s": ("fuzz", "not preserved: d8"),
    "bad_sp.s": ("fuzz", "not preserved: sp"),
    "bad_infinite_loop.s": ("fuzz", "timeout"),
}


def wrap_baseline(builder: Builder, task, body: str) -> str:
    """The compiler's assembly for ref.c, renamed to a local `inner`, plus a hand-written
    exported wrapper `body` that calls it. Lets a test inject one precise bug into any task."""
    sym = builder.target.symbol_prefix + task.symbol
    asm = builder.baseline_asm(task)
    asm = re.sub(r"^\s*\.globl\s+%s\b.*$" % re.escape(sym), "", asm, flags=re.M)
    asm = re.sub(r"(?<![\w.$])%s(?![\w.$])" % re.escape(sym), "inner_impl", asm)
    asm = re.sub(r"^\s*\.subsections_via_symbols.*$", "", asm, flags=re.M)
    return "%s\n    .text\n    .globl %s\n    .p2align 2\n%s:\n%s\n" % (asm, sym, sym, body)


CALL_INNER = ("    stp     x29, x30, [sp, #-16]!\n    mov     x29, sp\n    bl      inner_impl\n"
              "    ldp     x29, x30, [sp], #16\n")


@unittest.skipIf(TARGET is None, "this machine's target is not supported by the harness yet")
class HarnessCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = Builder(ROOT, TARGET)
        cls.tmp = Path(tempfile.mkdtemp(prefix="vibeasm-test-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def task(self, name, timeout=1):
        t = copy.deepcopy(load_task(ROOT, name))
        t.fuzz["timeout"] = timeout          # keep the infinite-loop case fast
        return t

    def write(self, name: str, text: str) -> Path:
        p = self.tmp / name
        p.write_text(text)
        return p

    def assertRejected(self, res, stage: str, needle: str):
        report = res.text()
        self.assertFalse(res.ok, "should have been rejected:\n" + report)
        self.assertEqual(res.stage, stage, report)
        self.assertIn(needle, report)


class TestZoo(HarnessCase):
    """One wordcount implementation per bug class; each must die at the right gate."""

    def test_every_zoo_file_has_an_expectation(self):
        files = sorted(p.name for p in ZOO.glob("*.s"))
        self.assertEqual(files, sorted(EXPECT), "tests/zoo/wordcount and EXPECT are out of sync")

    def test_zoo(self):
        task = self.task("wordcount")
        for name, (stage, needle) in sorted(EXPECT.items()):
            with self.subTest(file=name):
                res = check(self.builder, task, ZOO / name, dump_dir=self.tmp / "dump")
                report = res.text()
                self.assertEqual(res.stage, stage, report)
                self.assertEqual(res.ok, stage == "passed", report)
                self.assertIn(needle, report)

    def test_crash_report_points_at_the_source_line(self):
        res = check(self.builder, self.task("wordcount"), ZOO / "bad_overread.s", dump_dir=self.tmp / "dump")
        report = res.text()
        self.assertIn("bad_overread.s:7", report)          # the ldr that over-reads
        self.assertRegex(report, r"=>\s+4:\s+ldr\s+x9, \[x0\]")
        self.assertIn("in+0", report)                      # x0 annotated relative to the buffer
        self.assertTrue((self.tmp / "dump" / "input.bin").exists(), "failing input should be saved")

    def test_hold_out_seed_changes_the_cases(self):
        task = self.task("wordcount")
        a = check(self.builder, task, ZOO / "ok_scalar.s", seed=1)
        b = check(self.builder, task, ZOO / "ok_scalar.s", seed=2, profile="full")
        self.assertTrue(a.ok and b.ok)
        self.assertGreater(b.cases, a.cases)


class TestAllTasks(HarnessCase):
    """Every task must accept the compiler's own output for its reference -- and reject
    the same code with one bug injected through a wrapper."""

    def test_compiler_output_passes_every_task(self):
        for name in list_tasks(ROOT):
            with self.subTest(task=name):
                task = self.task(name)
                src = self.write("%s_compiler.s" % name, self.builder.baseline_asm(task))
                res = check(self.builder, task, src)
                self.assertTrue(res.ok, res.text())
                self.assertGreater(res.cases, 100)

    def test_bytes_to_bytes_bugs(self):
        task = self.task("base64_encode")
        cases = {
            "wrong_len": (CALL_INNER + "    add     x0, x0, #1\n    ret", "bytes written"),
            "wrong_bytes": ("    stp     x29, x30, [sp, #-32]!\n    mov     x29, sp\n    str     x2, [sp, #16]\n"
                            "    bl      inner_impl\n    ldr     x9, [sp, #16]\n    cmp     x0, #40\n    b.lo    1f\n"
                            "    mov     w10, #'?'\n    strb    w10, [x9, #37]\n1:\n"
                            "    ldp     x29, x30, [sp], #32\n    ret", "output differs from the reference at byte 37"),
            "dst_underflow": ("    sturb   wzr, [x2, #-1]\n" + CALL_INNER + "    ret", "output buffer"),
            "dst_overflow": ("    stp     x29, x30, [sp, #-32]!\n    mov     x29, sp\n    str     x2, [sp, #16]\n"
                             "    bl      inner_impl\n    ldr     x9, [sp, #16]\n    strb    wzr, [x9, x0]\n"
                             "    ldp     x29, x30, [sp], #32\n    ret", "output buffer"),
        }
        for label, (body, needle) in cases.items():
            with self.subTest(bug=label):
                res = check(self.builder, task, self.write("b64_%s.s" % label, wrap_baseline(self.builder, task, body)))
                self.assertRejected(res, "fuzz", needle)

    def test_ints_bugs(self):
        task = self.task("nqueens")
        wrong = CALL_INNER + "    cmp     x0, #40\n    cinc    x0, x0, eq\n    ret"   # nqueens(7) == 40
        res = check(self.builder, task, self.write("nq_wrong.s", wrap_baseline(self.builder, task, wrong)))
        self.assertRejected(res, "fuzz", "expected 40")
        self.assertIn("n=7", res.text())
        clobber = CALL_INNER + "    mov     x27, #0\n    ret"
        res = check(self.builder, task, self.write("nq_abi.s", wrap_baseline(self.builder, task, clobber)))
        self.assertRejected(res, "fuzz", "not preserved: x27")

    def test_answer_table_is_refused(self):
        task = self.task("nqueens")
        cheat = "    cmp     x0, #12\n    b.ne    1f\n    mov     x0, #14200\n    ret\n1:\n" + CALL_INNER + "    ret"
        res = check(self.builder, task, self.write("nq_cheat.s", wrap_baseline(self.builder, task, cheat)))
        self.assertRejected(res, "lint", "one of this task's answers")

    def test_briefs_render_for_every_task(self):
        for name in list_tasks(ROOT):
            task = self.task(name)
            for agentic in (True, False):
                with self.subTest(task=name, agentic=agentic):
                    brief = build_brief(self.builder, task, agentic=agentic)
                    self.assertNotRegex(brief, r"\{[a-z_]+\}", "unfilled placeholder in the brief")
                    self.assertIn(task.signature(), brief)
                    self.assertIn("_" + task.symbol, brief)
                    self.assertEqual("vibeasm bench" in brief, agentic)


class TestLint(unittest.TestCase):
    def test_directives(self):
        self.assertTrue(lint_source("    .arch armv9-a\n"))
        self.assertTrue(lint_source("foo: .incbin \"x\"\n"))
        self.assertFalse(lint_source("    // .arch in a comment\n    /* .cpu\n .arch */ nop\n"))
        self.assertFalse(lint_source("    .ascii \".arch\"\n"))

    def test_forbidden_constants(self):
        self.assertTrue(lint_source("    mov x0, #14200\n", [14200]))
        self.assertTrue(lint_source("    .long 0x3778\n", [14200]))
        self.assertFalse(lint_source("    mov x0, #1420\n    b L14200\n", [14200]))
        self.assertFalse(lint_source("    mov x0, #1 // 14200\n", [14200]))

    def test_extract_code_block(self):
        reply = "Plan:\n```\nnot this\n```\nFinal:\n```asm\n    ret\n```\nDone."
        self.assertEqual(extract_code_block(reply), "    ret\n")
        self.assertEqual(extract_code_block("no code here"), "")


class TestLoop(HarnessCase):
    """The round loop with a scripted agent: a rejected round must produce feedback, and
    a later correct round must be accepted on the harness's own verification."""

    def run_mock(self, extra: str, name: str):
        task = self.task("wordcount")
        mock = "%s %s %s %s %s" % (sys.executable, ROOT / "tests" / "mock_agent.py", extra,
                                   ZOO / "bad_overread.s", ZOO / "ok_scalar.s")
        lines = []
        res = run_task(self.builder, task, CommandAgent(mock), rounds=3, fresh=True, do_install=False,
                       run_dir=self.tmp / name, say=lines.append, stop_at_goal=False)
        return res, "\n".join(lines)

    def test_rejects_then_accepts(self):
        res, log = self.run_mock("", "run-edit")
        self.assertTrue(res.ok, log)
        self.assertEqual([r["verified"] for r in res.rounds], [False, True, True])
        self.assertTrue(res.rounds[1].get("new_best"))
        self.assertFalse(res.rounds[2].get("new_best"), "an identical file is not an improvement")
        brief2 = (res.run_dir / "rounds" / "02" / "brief.md").read_text()
        self.assertIn("rejected", brief2)
        self.assertIn("PAST THE END of the input buffer", brief2)
        notes = (res.run_dir / "work" / "NOTES.md").read_text()
        self.assertIn("Round 1 -- harness verdict", notes)
        self.assertIn("Round 2 -- harness verdict", notes)
        self.assertEqual((res.run_dir / "best.s").read_text(), (ZOO / "ok_scalar.s").read_text())

    def test_reply_with_a_code_block_instead_of_editing(self):
        res, log = self.run_mock("--print", "run-print")
        self.assertTrue(res.ok, log)
        self.assertEqual([r["verified"] for r in res.rounds], [False, True, True])

    def test_judge_is_independent_of_the_agent(self):
        v = judge(self.builder, self.task("wordcount"), ZOO / "bad_overflow_large.s")
        self.assertFalse(v.ok)
        v = judge(self.builder, self.task("wordcount"), ZOO / "ok_scalar.s")
        self.assertTrue(v.ok)
        self.assertEqual(len(set(v.seeds)), 2)
        self.assertGreater(v.cases, 10000)


class TestLoopRecovery(HarnessCase):
    """Resuming a run, and a winner that fails its final verification."""

    def private_root(self, name: str) -> Path:
        """A throwaway repository root with a copy of the wordcount task, so that
        installing a solution does not touch the real solutions/ directory."""
        root = self.tmp / name
        shutil.copytree(ROOT / "tasks" / "wordcount", root / "tasks" / "wordcount")
        return root

    def test_resume_continues_in_the_same_work_directory(self):
        root = self.private_root("resume-root")
        builder = Builder(root, TARGET)
        task = load_task(root, "wordcount")
        mock = "%s %s %s %s" % (sys.executable, ROOT / "tests" / "mock_agent.py",
                                ZOO / "bad_wrong_result.s", ZOO / "ok_scalar.s")
        quiet = lambda _text: None  # noqa: E731
        first = run_task(builder, task, CommandAgent(mock), rounds=1, fresh=True, do_install=False, say=quiet)
        self.assertFalse(first.ok)
        again = run_task(builder, task, CommandAgent(mock), rounds=1, do_install=True, say=quiet, resume=True)
        self.assertEqual(again.run_dir, first.run_dir)
        self.assertTrue(again.ok, again.message)
        self.assertEqual([r["round"] for r in again.rounds], [1, 2])
        self.assertIn("rejected", (again.run_dir / "rounds" / "02" / "brief.md").read_text())
        installed = root / "solutions" / TARGET.name / "wordcount.s"
        self.assertEqual(installed.read_text(), (ZOO / "ok_scalar.s").read_text())
        record = __import__("json").loads(installed.with_suffix(".json").read_text())
        self.assertEqual(record["agent"]["rounds"], 2)
        self.assertGreater(record["verified"]["test_cases"], 100000)

    def test_a_winner_that_fails_final_verification_is_never_installed(self):
        from unittest import mock as umock
        import vibeasm.loop as loop

        root = self.private_root("final-root")
        builder = Builder(root, TARGET)
        task = load_task(root, "wordcount")
        agent = CommandAgent("%s %s %s" % (sys.executable, ROOT / "tests" / "mock_agent.py", ZOO / "ok_scalar.s"))
        real_judge = loop.judge
        calls = []

        def flaky_judge(*args, **kwargs):
            calls.append(kwargs.get("samples"))
            v = real_judge(*args, **kwargs)
            if kwargs.get("samples") == 101:          # the final verification: pretend a rare bug showed up
                bad = loop.CheckResult(False, "fuzz", "wrong result on test case #99999", "  (simulated rare failure)")
                return loop.Verdict(False, bad, seeds=v.seeds)
            return v

        lines = []
        with umock.patch.object(loop, "judge", flaky_judge):
            res = run_task(builder, task, agent, rounds=1, fresh=True, do_install=True, say=lines.append,
                           stop_at_goal=False)
        self.assertFalse(res.ok)
        self.assertIn("failed final verification", res.message)
        self.assertFalse((root / "solutions" / TARGET.name / "wordcount.s").exists(), "must not be installed")
        notes = (res.run_dir / "work" / "NOTES.md").read_text()
        self.assertIn("Final verification -- REJECTED", notes)
        self.assertEqual(res.rounds[-1]["round"], "final")

    def test_agent_spend_limit_stops_without_judging_untouched_baseline(self):
        from unittest import mock as umock
        import vibeasm.loop as loop

        root = self.private_root("quota-root")
        builder = Builder(root, TARGET)
        task = load_task(root, "wordcount")
        agent = CommandAgent("sh -c 'cat >/dev/null; echo \"You have hit your spend limit\"; exit 1'")
        lines = []
        with umock.patch.object(loop, "judge", side_effect=AssertionError("judge must not run on untouched baseline")):
            res = run_task(builder, task, agent, rounds=3, fresh=True, do_install=False, say=lines.append)
        self.assertFalse(res.ok)
        self.assertEqual(len(res.rounds), 1, "fatal quota error must stop the round loop early")
        self.assertFalse(res.rounds[0]["agent_ok"])
        self.assertFalse(res.rounds[0]["verified"])
        self.assertIn("spend limit", res.rounds[0]["agent_error"])
        self.assertTrue(any("agent error:" in ln and "spend limit" in ln for ln in lines))


FAKE_CLAUDE = """#!/bin/sh
# stands in for `claude -p ... --output-format stream-json`: emits the event shapes the
# harness has met, including the ones that once crashed it
echo '{"type":"system","subtype":"init","model":"fake"}'
echo '{"type":"system","subtype":"permission_denied","tool_name":"Bash","message":"denied","decision_reason":"no approval surface"}'
echo 'not json at all'
echo '[1,2,3]'
echo '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"Bash","input":{"command":"vibeasm check"}}]}}'
echo '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"PASS  solution.s: ok"}]}}'
echo "noise on stderr" >&2
if [ -n "$FAKE_CLAUDE_HANG" ]; then sleep 60; fi
echo "$VIBEASM_SANDBOX" > sandbox-flag.txt
echo '{"type":"result","subtype":"success","is_error":false,"result":"done","total_cost_usd":0.5,"num_turns":3,"modelUsage":{"fake-model":{}}}'
"""


class TestClaudeBackend(unittest.TestCase):
    """The plumbing around a headless agent, with a stand-in `claude` on PATH."""

    def setUp(self):
        from vibeasm.agent import ClaudeCodeAgent
        self.Agent = ClaudeCodeAgent
        self.tmp = Path(tempfile.mkdtemp(prefix="vibeasm-fake-claude-"))
        fake = self.tmp / "bin" / "claude"
        fake.parent.mkdir()
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(0o755)
        self.old_env = dict(os.environ)
        os.environ["PATH"] = str(fake.parent) + os.pathsep + os.environ["PATH"]
        self.work = self.tmp / "work"
        self.work.mkdir()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stream_is_logged_summarized_and_survives_odd_events(self):
        notes = []
        r = self.Agent(timeout_s=30).run(self.work, ROOT, self.tmp / "agent.log", on_event=notes.append)
        self.assertTrue(r.ok, r.error)
        self.assertEqual((r.message, r.turns, r.cost_usd, r.model), ("done", 3, 0.5, "fake-model"))
        joined = "\n".join(notes)
        self.assertIn("sandbox denied a Bash call", joined)
        self.assertRegex(joined, r"\$ vibeasm check\s+PASS")
        self.assertIn("not json at all", (self.tmp / "agent.log").read_text())
        self.assertEqual((self.work / "sandbox-flag.txt").read_text().strip(), "1",
                         "the agent's environment must carry the sandbox flag")

    def test_a_silent_agent_is_stopped_at_the_time_limit(self):
        os.environ["FAKE_CLAUDE_HANG"] = "1"
        import time as _time
        t0 = _time.time()
        r = self.Agent(timeout_s=2).run(self.work, ROOT, self.tmp / "agent.log")
        self.assertFalse(r.ok)
        self.assertIn("exceeded 2 s", r.error)
        self.assertLess(_time.time() - t0, 15)

    def test_command_line_confines_the_agent(self):
        cmd = self.Agent(model="m", max_budget_usd=3).command()
        for flag in ("--safe-mode", "--restricted", "--no-session-persistence"):
            self.assertIn(flag, cmd)
        self.assertIn("Bash(vibeasm *)", cmd)
        self.assertEqual(cmd[cmd.index("--permission-prompts") + 1], "none")
        self.assertNotIn("--dangerously-skip-permissions", cmd)


class TestCli(HarnessCase):
    def vibeasm(self, *args, env=None, cwd=None):
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run([sys.executable, str(ROOT / "bin" / "vibeasm"), *args], capture_output=True,
                              text=True, env=e, cwd=cwd)

    def test_check_exit_codes(self):
        self.assertEqual(self.vibeasm("check", "wordcount", str(ZOO / "ok_scalar.s")).returncode, 0)
        p = self.vibeasm("check", "wordcount", str(ZOO / "bad_wrong_result.s"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("FAIL", p.stdout)

    def test_call(self):
        p = self.vibeasm("call", "wordcount", str(ZOO / "ok_scalar.s"), "--text", "the quick\\tbrown\\nfox")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("returns 4", p.stdout)
        p = self.vibeasm("call", "wordcount", str(ZOO / "bad_wrong_result.s"), "--hex", "610e62")
        self.assertEqual(p.returncode, 1)
        self.assertIn("DIFF", p.stdout)

    def test_call_with_a_generated_input(self):
        p = self.vibeasm("call", "wordcount", str(ZOO / "bad_real_lane_overflow.s"), "--gen", "16177", "--flavor", "4")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("reference returns 8089", p.stdout)
        p = self.vibeasm("call", "wordcount", str(ZOO / "ok_scalar.s"), "--gen", "16177", "--flavor", "4")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_bench_with_rivals(self):
        src = self.write("crc_compiler.s", self.builder.baseline_asm(self.task("crc32")))
        p = self.vibeasm("bench", "crc32", str(src), "--rivals", "--samples", "5", "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        out = __import__("json").loads(p.stdout)
        self.assertIn("zlib", out["cands"])
        self.assertGreater(out["scores"]["zlib"], 2.0, "the system zlib should beat a table-driven loop")
        self.assertAlmostEqual(out["scores"]["crc_compiler"], 1.0, delta=0.35)

    def test_agent_sandbox_cannot_run_or_install(self):
        for cmd in (["run", "wordcount"], ["accept", "wordcount", "x.s"], ["new", "x"]):
            p = self.vibeasm(*cmd, env={"VIBEASM_SANDBOX": "1"})
            self.assertEqual(p.returncode, 2)
            self.assertIn("not available inside an agent session", p.stderr)

    def test_work_directory_implies_the_task(self):
        work = self.tmp / "work"
        p = self.vibeasm("work", "crc32", str(work))
        self.assertEqual(p.returncode, 0, p.stderr)
        for f in ("TASK.md", "ABI.md", "ref.c", "baseline.s", "solution.s", "NOTES.md", "SPEC.md"):
            self.assertTrue((work / f).exists(), f)
        # whatever `work` seeded solution.s with, a function that just returns 0 must fail here
        (work / "solution.s").write_text("    .text\n    .globl _crc32_ieee\n_crc32_ieee:\n    mov x0, #0\n    ret\n")
        p = self.vibeasm("check", cwd=str(work))       # no task argument: the directory implies it
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("wrong result", p.stdout)

    def test_new_task_scaffold_runs_end_to_end(self):
        root = self.tmp / "sandbox-root"
        (root / "tasks").mkdir(parents=True)
        for shape, args in (("bytes_to_u64", []), ("bytes_to_bytes", []), ("ints_to_u64", ["a", "b"])):
            with self.subTest(shape=shape):
                name = "demo_" + shape
                scaffold(root, name, shape, args)
                builder = Builder(root, TARGET)
                task = load_task(root, name)
                src = self.write(name + ".s", builder.baseline_asm(task))
                res = check(builder, task, src)
                self.assertTrue(res.ok, res.text())


if __name__ == "__main__":
    unittest.main()
