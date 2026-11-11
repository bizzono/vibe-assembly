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
        p = self.vibeasm("check", cwd=str(work))       # the starter returns 0: wrong, but well-formed
        self.assertEqual(p.returncode, 1)
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
