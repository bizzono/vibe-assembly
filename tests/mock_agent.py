#!/usr/bin/env python3
"""A scripted stand-in for an LLM agent, used to test the round loop without a model.

usage: mock_agent.py FILE [FILE ...]

Each time it is run in a work directory it "writes" the next FILE as solution.s (the
last one repeats). With `--print` it prints the file in a fenced block instead of
writing it, the way a plain chat model would.
"""
import shutil
import sys
from pathlib import Path

args = [a for a in sys.argv[1:] if a != "--print"]
as_reply = "--print" in sys.argv
state = Path(".mock-agent-round")
n = int(state.read_text()) if state.exists() else 0
state.write_text(str(n + 1))
src = Path(args[min(n, len(args) - 1)])
brief = sys.stdin.read()
assert "Hard rules" in brief, "the brief must arrive on stdin"
if as_reply:
    print("Here is my solution.\n\n```asm\n%s```" % src.read_text())
else:
    shutil.copyfile(src, "solution.s")
    print("mock agent: wrote %s as solution.s" % src.name)
