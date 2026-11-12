"""Agents: who writes the assembly.

The harness does not care which model or tool writes `solution.s`; it only believes
what it can verify. A backend's job is small: given a work directory with a brief in
it, make an agent work there and return when it is done.

Backends:
  claude   Claude Code, headless (`claude -p`). Agentic: it runs `vibeasm check` and
           `vibeasm bench` itself and iterates before handing back.
  cmd      Any command. The brief is on stdin and in TASK.md. If the command edits
           solution.s, good; if it prints a fenced code block instead, the last block
           becomes solution.s (so a plain chat model works too).
  manual   Nobody: the harness prepares the work directory and waits for you.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .build import Builder
from .task import Task

PROMPTS = Path(__file__).resolve().parent / "prompts"

AGENTIC_TOOLS = """\
Run these from the current directory. They are the only commands your shell will run
(plus read-only ones such as `cat` and `ls` inside this directory): anything else is
denied, and nobody is there to approve it. **Create and change files with your
file-editing tools, not with shell redirection, heredocs or `sed`.**

| command | what it does |
|---|---|
| `vibeasm check [file.s]` | assemble, lint, then run thousands of differential tests against the reference under guard pages and the ABI trampoline. About a second. On failure it prints the exact input, the faulting source line and the registers. Add `--full` for the long version. |
| `vibeasm bench [a.s b.s ...]` | check, then time against the compiler baseline. Several files are timed side by side in one process: this is how you compare variants. |
| `vibeasm call [file.s] {call_example} | run one input of your choosing through your code and the reference, and print both results.{gen_note} |
| `vibeasm disasm [file.s] --lines` | what your file assembled to, with source line numbers. |
| `vibeasm baseline` | the assembly the compiler generates for `ref.c` (also saved as `baseline.s`). |
| `vibeasm cpu` | CPU features of this machine and the subset you may assume. |

With no file argument the tools use `solution.s`."""

SWEEP_NOTE = """

   The check tries **every length** up to several thousand bytes with every kind of
   input (and windows around 8160, 16320, ... bytes), precisely because counters that
   overflow and tails that are off by one fail only for a few lengths. If you keep
   per-lane counters, work out the worst case on paper, *including the tail*."""

ONESHOT_TOOLS = """\
You cannot run anything in this session. Write the best `solution.s` you can from the
contract and the reference; the harness will assemble, test and time it and send the
results back for another round."""


@dataclass
class AgentResult:
    ok: bool
    message: str = ""            # the agent's final message
    error: str = ""
    cost_usd: float = 0.0
    turns: int = 0
    seconds: float = 0.0
    model: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


def build_brief(builder: Builder, task: Task, *, agentic: bool, feedback: str = "",
                best_score: Optional[float] = None) -> str:
    target = builder.target
    asm_symbol = target.symbol_prefix + task.symbol
    if task.shape == "bytes_to_u64":
        buffer_rule = (" Read only `buf[0 .. len)`; never write to it. Every test places the buffer flush "
                       "against an unmapped guard page (at the end, and at the start, in turn), so reading even "
                       "one byte outside it is a crash -- including inside a vector load, and including "
                       "`len == 0`.")
        call_example = "--text 'some bytes'` (or `--hex 00ff10`, `--input FILE`)"
        small = ", including the tiny inputs"
    elif task.shape == "bytes_to_bytes":
        buffer_rule = (" Read only `src[0 .. len)` and never write to it; write only inside `dst`, whose capacity "
                       "is exactly what the contract says. Both buffers are placed flush against unmapped guard "
                       "pages (at the end, and at the start, in turn), so one byte outside either is a crash -- "
                       "including inside a vector load or store, and including `len == 0`.")
        call_example = "--text 'some bytes'` (or `--hex 00ff10`, `--input FILE`)"
        small = ", including the tiny inputs"
    else:
        buffer_rule = (" This function takes integers and touches no caller memory. Use registers and, if "
                       "you need it, your own stack frame.")
        call_example = "--args %s`" % ",".join("8" for _ in task.args)
        small = ""

    rows = []
    for bc in task.bench:
        if task.is_bytes:
            flavor = ""
            if bc.flavor:
                flavor = " (input flavor %d)" % bc.flavor
            rows.append("- `%s`: %d bytes%s" % (bc.name, bc.size, flavor))
        else:
            rows.append("- `%s`: %s" % (bc.name, ", ".join("%s=%d" % (n, v) for n, v in zip(task.args, bc.args))))

    extra_rules = ""
    if task.forbid_constants:
        extra_rules = ("6. **Compute, do not look up.** The answers of this task may not appear in your file as "
                       "constants; the harness scans for them.\n")

    best_note = ""
    if best_score:
        best_note = (" The best verified solution so far scores **%.2fx**; it is in `best.s`. Beat it, or explain "
                     "in your final message why it cannot be beaten." % best_score)

    deliver = ("A starter `solution.s` with the right directives is already there."
               if agentic else
               "Reply with the complete file in a single fenced code block (```asm ... ```), and nothing after it.")

    gen_note = ""
    if task.is_bytes:
        from .gates import flavors
        names = flavors(builder, task)
        gen_note = (" `--gen SIZE --flavor N` builds an input of exactly SIZE bytes with the test generator "
                    "(flavors: %s), for probing one length or one kind of input."
                    % ", ".join("%d = %s" % (i, n) for i, n in enumerate(names)))
    tools = (AGENTIC_TOOLS.replace("{call_example}", call_example).replace("{gen_note}", gen_note)
             if agentic else ONESHOT_TOOLS)
    text = (PROMPTS / "brief.md").read_text()
    fields = {
        "symbol": task.symbol, "asm_symbol": asm_symbol, "target": target.name,
        "baseline_desc": builder.baseline_description(), "signature": task.signature(),
        "spec": _demote_headings(task.spec_path.read_text().strip()), "deliver_note": deliver,
        "buffer_rule": buffer_rule, "features": target.feature_baseline, "extra_rules": extra_rules,
        "tools": tools, "small_note": small, "bench_cases": "\n".join(rows),
        "sweep_note": SWEEP_NOTE if task.is_bytes else "",
        "goal": "%g" % task.goal_speedup, "best_note": best_note,
        "feedback": ("## Where things stand\n\n" + feedback.strip() + "\n\n") if feedback.strip() else "",
    }
    for k, v in fields.items():
        text = text.replace("{" + k + "}", v)
    if not agentic:
        # the "how to work" steps that need tools make no sense without them
        text = re.sub(r"\n## How to work\n.*?(?=\n## )", "\n", text, flags=re.S)
    return text


def _demote_headings(md: str) -> str:
    """The spec is embedded under a heading of the brief, so push its headings down two levels
    and drop its title and prototype (the brief already shows them)."""
    lines = md.splitlines()
    out, in_code, skipped_title, skipped_proto = [], False, False, False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            if not in_code and not skipped_proto and line.strip() == "```c":
                # first C block is the prototype: skip it
                j = i + 1
                while j < len(lines) and not lines[j].startswith("```"):
                    j += 1
                skipped_proto = True
                i = j + 1
                continue
            in_code = not in_code
        if not in_code and line.startswith("# ") and not skipped_title:
            skipped_title = True
            i += 1
            continue
        if not in_code and re.match(r"#{1,4} ", line):
            line = "##" + line
        out.append(line)
        i += 1
    return "\n".join(out).strip()


def starter(builder: Builder, task: Task) -> str:
    sym = builder.target.symbol_prefix + task.symbol
    return ("// %s -- %s\n// %s\n//\n// Starter file: it assembles, but returns immediately. Replace the body.\n"
            "    .text\n    .globl  %s\n    .p2align 4\n%s:\n    mov     x0, #0\n    ret\n"
            % (task.name, task.summary, task.signature(), sym, sym))


# ---- backends -----------------------------------------------------------------------

def _child_env(root: Path) -> Dict[str, str]:
    env = dict(os.environ)
    # A nested agent session must not think it is a child of whatever launched the harness.
    for k in list(env):
        if k == "CLAUDECODE" or k.startswith("CLAUDE_CODE_") or k in ("CLAUDE_PID", "CLAUDE_EFFORT"):
            del env[k]
    env["PATH"] = str(root / "bin") + os.pathsep + env.get("PATH", "")
    env["VIBEASM_ROOT"] = str(root)
    env["VIBEASM_SANDBOX"] = "1"   # the agent may only use the read/verify commands
    return env


class ClaudeCodeAgent:
    """Claude Code in headless mode, confined to the work directory.

    Permissions: file tools limited to the work directory (--restricted), no user
    customizations (--safe-mode), and the only non-read-only command it may run is
    `vibeasm`. Nothing that would need a permission prompt is ever approved.
    """

    name = "claude"
    agentic = True

    def __init__(self, model: str = "", effort: str = "", max_budget_usd: float = 0.0,
                 timeout_s: int = 3600, extra_args: Optional[List[str]] = None):
        self.model, self.effort, self.max_budget_usd = model, effort, max_budget_usd
        self.timeout_s = timeout_s
        self.extra_args = extra_args or []

    def available(self) -> Optional[str]:
        return None if shutil.which("claude") else "the `claude` command (Claude Code) is not on PATH"

    def command(self) -> List[str]:
        cmd = ["claude", "-p", "Read TASK.md in the current directory and carry out the task it describes.",
               "--output-format", "stream-json", "--verbose",
               "--safe-mode", "--restricted",
               "--tools", "Read,Write,Edit,Glob,Grep,Bash",
               "--allowedTools", "Read", "Write", "Edit", "Glob", "Grep", "Bash(vibeasm *)",
               "--permission-mode", "acceptEdits", "--permission-prompts", "none",
               "--no-session-persistence"]
        if self.model:
            cmd += ["--model", self.model]
        if self.effort:
            cmd += ["--effort", self.effort]
        if self.max_budget_usd > 0:
            cmd += ["--max-budget-usd", "%g" % self.max_budget_usd]
        return cmd + self.extra_args

    def run(self, workdir: Path, root: Path, log_path: Path,
            on_event: Optional[Callable[[str], None]] = None) -> AgentResult:
        t0 = time.time()
        err_path = log_path.with_suffix(".stderr")
        try:
            with open(err_path, "w") as err:
                proc = subprocess.Popen(self.command(), cwd=str(workdir), env=_child_env(root),
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
                                        text=True, errors="replace", start_new_session=True)
        except FileNotFoundError:
            return AgentResult(False, error="`claude` not found")
        timed_out = threading.Event()

        def stop() -> None:              # the session ran out of time: end it, whatever it is doing
            timed_out.set()
            _kill_group(proc)

        watchdog = threading.Timer(self.timeout_s, stop)
        watchdog.daemon = True
        watchdog.start()
        try:
            result = self._pump(proc, log_path, on_event)
        finally:
            watchdog.cancel()
            if proc.poll() is None:      # we are leaving early (error, Ctrl-C): do not orphan the agent
                _kill_group(proc)
        secs = time.time() - t0
        if timed_out.is_set():
            return AgentResult(False, error="agent session exceeded %d s and was stopped" % self.timeout_s, seconds=secs)
        if not result:
            try:
                tail = err_path.read_text(errors="replace").strip()[-500:]
            except OSError:
                tail = ""
            return AgentResult(False, error="agent produced no result (exit %s): %s" % (proc.returncode, tail), seconds=secs)
        models = list((result.get("modelUsage") or {}).keys())
        return AgentResult(ok=not result.get("is_error", False), message=str(result.get("result", "")),
                           error=str(result.get("result", "")) if result.get("is_error") else "",
                           cost_usd=float(result.get("total_cost_usd") or 0.0), turns=int(result.get("num_turns") or 0),
                           seconds=secs, model=self.model or (models[0] if models else ""),
                           meta={"subtype": result.get("subtype"), "models": models,
                                 "denials": len(result.get("permission_denials") or [])})

    @staticmethod
    def _pump(proc, log_path: Path, on_event) -> Dict[str, Any]:
        """Copy the agent's event stream to the log, report the interesting events, and
        return the final `result` event (empty if the session ended without one)."""
        result: Dict[str, Any] = {}
        calls: Dict[str, str] = {}
        with open(log_path, "w") as log:
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                log.flush()
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(ev, dict):
                    continue
                if ev.get("type") == "result":
                    result = ev
                elif on_event:
                    try:
                        note = _summarize_stream_event(ev, calls)
                    except Exception:      # an event shape we do not know: the log has it, move on
                        note = ""
                    if note:
                        on_event(note)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
        return result


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def _summarize_stream_event(ev: Dict[str, Any], calls: Dict[str, str]) -> str:
    """One short line for the things worth watching live: tool runs and their verdicts."""
    if ev.get("type") == "system" and ev.get("subtype") == "permission_denied":
        return "  (sandbox denied a %s call: %s)" % (ev.get("tool_name"), str(ev.get("decision_reason", ""))[:80])
    msg = ev.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, list):
        return ""
    notes = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if ev.get("type") == "assistant" and block.get("type") == "tool_use":
            inp = block.get("input") or {}
            name = block.get("name")
            if name == "Bash":
                cmd = str(inp.get("command", "")).strip().splitlines()[0][:100] if inp.get("command") else ""
                calls[str(block.get("id"))] = cmd
            elif name in ("Write", "Edit"):
                notes.append("  %s %s" % ("wrote" if name == "Write" else "edited", Path(str(inp.get("file_path", "?"))).name))
        elif ev.get("type") == "user" and block.get("type") == "tool_result":
            cmd = calls.pop(str(block.get("tool_use_id")), "")
            if cmd.startswith("vibeasm"):
                body = block.get("content")
                if isinstance(body, list):
                    body = "".join(str(b.get("text", "")) for b in body if isinstance(b, dict))
                verdict = _first_verdict(str(body or ""))
                notes.append("  $ %-42s %s" % (cmd[:42], verdict))
    return "\n".join(notes)


def _first_verdict(text: str) -> str:
    lines = [l for l in text.strip().splitlines() if l.strip()]
    for l in lines:
        if l.startswith("PASS") or l.startswith("FAIL"):
            return l[:110]
    for l in lines:
        if l.startswith("geomean"):
            return " ".join(l.split())[:110]
    return lines[0][:110] if lines else ""


class CommandAgent:
    """Any command-line agent or model. The brief is piped to stdin; {workdir} and
    {brief} in the command template are replaced with paths."""

    name = "cmd"

    def __init__(self, template: str, agentic: bool = False, timeout_s: int = 3600):
        self.template, self.agentic, self.timeout_s = template, agentic, timeout_s

    def available(self) -> Optional[str]:
        return None if self.template.strip() else "no command given (use --agent-cmd)"

    def run(self, workdir: Path, root: Path, log_path: Path,
            on_event: Optional[Callable[[str], None]] = None) -> AgentResult:
        brief = workdir / "TASK.md"
        cmd = self.template.replace("{workdir}", shlex.quote(str(workdir))).replace("{brief}", shlex.quote(str(brief)))
        before = (workdir / "solution.s").read_bytes() if (workdir / "solution.s").exists() else b""
        t0 = time.time()
        try:
            p = subprocess.run(["/bin/sh", "-c", cmd], cwd=str(workdir), env=_child_env(root),
                               input=brief.read_text(), capture_output=True, text=True, errors="replace",
                               timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            return AgentResult(False, error="agent command exceeded %d s" % self.timeout_s, seconds=time.time() - t0)
        log_path.write_text(p.stdout + ("\n--- stderr ---\n" + p.stderr if p.stderr else ""))
        after = (workdir / "solution.s").read_bytes() if (workdir / "solution.s").exists() else b""
        if after == before:
            block = extract_code_block(p.stdout)
            if block:
                (workdir / "solution.s").write_text(block)
        if p.returncode != 0 and after == before and not extract_code_block(p.stdout):
            detail = (p.stderr.strip() or p.stdout.strip())[-400:]
            return AgentResult(False, error="agent command failed (exit %d): %s" % (p.returncode, detail),
                               seconds=time.time() - t0)
        return AgentResult(True, message=p.stdout.strip()[-2000:], seconds=time.time() - t0)


def extract_code_block(text: str) -> str:
    """The last fenced code block of a reply, without its fence."""
    blocks = re.findall(r"```[A-Za-z0-9_+-]*[ \t]*\n(.*?)```", text, flags=re.S)
    return blocks[-1].rstrip() + "\n" if blocks else ""


class ManualAgent:
    """No agent: a person (or an interactive agent session) works in the directory."""

    name = "manual"
    agentic = True

    def available(self) -> Optional[str]:
        return None

    def run(self, workdir: Path, root: Path, log_path: Path,
            on_event: Optional[Callable[[str], None]] = None) -> AgentResult:
        print("\nWork directory ready: %s" % workdir)
        print("Edit solution.s there (the brief is TASK.md), using `vibeasm check` and `vibeasm bench`.")
        try:
            input("Press Enter here when solution.s is ready to be judged... ")
        except EOFError:
            pass
        return AgentResult(True, message="(manual)")
