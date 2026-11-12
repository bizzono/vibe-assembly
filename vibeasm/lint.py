"""Static lint: what a solution is not allowed to be, checked before any of it runs.

A solution must be a pure, self-contained leaf of machine code:

  * it exports exactly one symbol, the task's function;
  * it references nothing outside itself (no libc, no calling the reference);
  * it has no writable data, so it cannot keep state between calls -- which makes
    "remember the benchmark's answer" structurally impossible, and makes it thread-safe;
  * it does not trap into the kernel or touch system registers;
  * it does not use x18, which Apple platforms reserve;
  * it does not switch the assembler to a newer CPU than the target baseline.

These are deliberately mechanical. They do not prove the code correct -- the
differential fuzzer does the convincing -- they remove whole classes of cheating and
of "works on my machine".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from .target import Target
from .util import ToolError, must

FORBIDDEN_DIRECTIVES = {
    ".arch": "selects a CPU architecture (the harness pins the feature baseline)",
    ".arch_extension": "enables a CPU extension (the harness pins the feature baseline)",
    ".cpu": "selects a CPU (the harness pins the feature baseline)",
    ".include": "pulls in another file (a solution is one self-contained file)",
    ".incbin": "pulls in another file (a solution is one self-contained file)",
}

FORBIDDEN_MNEMONICS = {
    "svc": "system call", "hvc": "hypervisor call", "smc": "secure monitor call",
    "eret": "exception return", "hlt": "halt", "wfi": "wait for interrupt", "wfe": "wait for event",
    "smstart": "SME is outside the feature baseline", "smstop": "SME is outside the feature baseline",
    "sys": "system instruction", "sysl": "system instruction",
    "syscall": "system call", "sysenter": "system call", "int": "software interrupt",
    "int3": "breakpoint trap", "ud2": "undefined instruction trap",
    "rdmsr": "model-specific register read", "wrmsr": "model-specific register write",
}

ALLOWED_SEGMENTS = {"__TEXT", "__DWARF", "__LD"}


@dataclass
class LintResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: Dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _strip_comment(line: str) -> str:
    # good enough for directives: cut // and ; comments that are not inside a string
    out, in_str = [], False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"':
            in_str = not in_str
        if not in_str and (line.startswith("//", i) or c == ";"):
            break
        out.append(c)
        i += 1
    return "".join(out)


def lint_source(text: str, forbid_constants: Sequence[int] = ()) -> List[str]:
    errors = []
    in_block = False
    forbidden = set(int(x) for x in forbid_constants)
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw
        if in_block:
            if "*/" in line:
                line = line.split("*/", 1)[1]
                in_block = False
            else:
                continue
        while "/*" in line:
            head, _, tail = line.partition("/*")
            if "*/" in tail:
                line = head + " " + tail.split("*/", 1)[1]
            else:
                line = head
                in_block = True
        code = _strip_comment(line)
        if forbidden:
            for tok in re.findall(r"(?<![\w.$])(0[xX][0-9a-fA-F]+|\d+)(?![\w.$])", code):
                try:
                    value = int(tok, 0)
                except ValueError:
                    continue  # e.g. a leading-zero decimal
                if value in forbidden:
                    errors.append("line %d: the constant %s is one of this task's answers. The task requires "
                                  "computing results, not looking them up." % (n, tok))
        m = re.match(r"\s*(?:[A-Za-z_.$][\w.$]*:\s*)*(\.[A-Za-z_]+)\b", code)
        if m and m.group(1).lower() in FORBIDDEN_DIRECTIVES:
            d = m.group(1).lower()
            errors.append("line %d: directive %s is not allowed: it %s" % (n, d, FORBIDDEN_DIRECTIVES[d]))
    return errors


def _sections(obj: Path) -> List[Tuple[str, str, int]]:
    """(segment, section, size) for every section of a Mach-O object."""
    out = must(["otool", "-l", obj], what="otool")
    result, sect, seg = [], None, None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "sectname":
            sect = parts[1]
        elif len(parts) >= 2 and parts[0] == "segname" and sect is not None:
            seg = parts[1]
        elif len(parts) >= 2 and parts[0] == "size" and sect is not None and seg is not None:
            result.append((seg, sect, int(parts[1], 16)))
            sect = seg = None
    return result


def parse_disassembly(text: str) -> List[Tuple[int, str, str]]:
    """(address, mnemonic, operands) for each decoded instruction of an objdump listing."""
    insns = []
    for line in text.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
        if m:
            ops = m.group(3).split(";")[0].strip()
            insns.append((int(m.group(1), 16), m.group(2).lower(), ops))
    return insns


def _sections_elf(obj: Path) -> Tuple[int, List[Tuple[str, int]]]:
    """Return (code_bytes, [(writable_section_name, size), ...]) for an ELF object via objdump -h."""
    out = must(["objdump", "-h", obj], what="objdump")
    code_bytes = 0
    writable: List[Tuple[str, int]] = []
    cur_sect, cur_size = None, 0
    for line in out.splitlines():
        m = re.match(r"^\s*\d+\s+(\S+)\s+([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+", line)
        if m:
            cur_sect, cur_size = m.group(1), int(m.group(2), 16)
            continue
        if cur_sect is not None:
            flags = {f.strip() for f in line.split(",")}
            if "CODE" in flags or cur_sect.startswith((".text", ".rodata")):
                code_bytes += cur_size
            is_writable_name = cur_sect.startswith((".data", ".bss", ".tdata", ".tbss"))
            is_writable_alloc = ("ALLOC" in flags and "READONLY" not in flags and "CODE" not in flags
                                 and not cur_sect.startswith((".note", ".eh_frame", ".comment")))
            if cur_size > 0 and (is_writable_name or is_writable_alloc):
                writable.append((cur_sect, cur_size))
            cur_sect = None
    return code_bytes, writable


def lint_object(target: Target, obj: Path, symbol: str, disassembly: str) -> LintResult:
    res = LintResult()
    want = target.symbol_prefix + symbol

    # exported / undefined symbols
    try:
        nm_def_cmd = ["nm", "-g", "-U", obj] if target.name.endswith("-darwin") else ["nm", "-g", "--defined-only", obj]
        defined = [l.split() for l in must(nm_def_cmd, what="nm").splitlines() if l.strip()]
        undefined = [l.split()[-1] for l in must(["nm", "-u", obj], what="nm").splitlines() if l.strip()]
    except ToolError as e:
        res.errors.append("could not inspect the object file: %s" % e)
        return res
    exported = [p[-1] for p in defined]
    text_exports = [p[-1] for p in defined if len(p) >= 2 and p[-2] == "T"]
    if want not in exported:
        res.errors.append("the object does not export %s. Add `.globl %s` and define the label `%s:`."
                          % (want, want, want))
    elif want not in text_exports:
        res.errors.append("%s is exported but is not code in the text section." % want)
    extra = [s for s in exported if s != want]
    if extra:
        res.errors.append("only %s may be exported, but the object also exports: %s. "
                          "Remove their .globl (plain labels stay local)." % (want, ", ".join(extra)))
    if undefined:
        res.errors.append("references to external symbols are not allowed (the solution must be "
                          "self-contained): %s" % ", ".join(undefined))

    # sections: code and read-only constants only
    try:
        if target.name.endswith("-darwin"):
            code_bytes = 0
            for seg, sect, size in _sections(obj):
                if seg == "__TEXT":
                    code_bytes += size
                if seg not in ALLOWED_SEGMENTS and size > 0:
                    res.errors.append("section %s,%s (%d bytes) is writable data. A solution may not keep state: "
                                      "put constants in `.section __TEXT,__const` and scratch space on the stack."
                                      % (seg, sect, size))
            res.info["text_bytes"] = code_bytes
        else:
            code_bytes, writable = _sections_elf(obj)
            for sect, size in writable:
                res.errors.append("section %s (%d bytes) is writable data. A solution may not keep state: "
                                  "put constants in `.section .rodata` and scratch space on the stack."
                                  % (sect, size))
            res.info["text_bytes"] = code_bytes
    except ToolError as e:
        res.errors.append("could not read section table: %s" % e)

    # instruction-level rules
    insns = parse_disassembly(disassembly)
    res.info["instructions"] = len(insns)
    seen = set()
    for addr, mn, ops in insns:
        base = mn.split(".")[0]
        if base in FORBIDDEN_MNEMONICS and base not in seen:
            seen.add(base)
            res.errors.append("instruction `%s %s` at +0x%x is not allowed (%s)."
                              % (mn, ops, addr, FORBIDDEN_MNEMONICS[base]))
        if base in ("msr", "mrs") and "nzcv" not in ops.lower() and ("sysreg", ops) not in seen:
            seen.add(("sysreg", ops))
            res.errors.append("instruction `%s %s` at +0x%x touches a system register; only NZCV is allowed."
                              % (mn, ops, addr))
        if target.name.endswith("-darwin") and re.search(r"\b[xw]18\b", ops) and "x18" not in seen:
            seen.add("x18")
            res.errors.append("instruction `%s %s` at +0x%x uses x18, which Apple platforms reserve. "
                              "Pick another register." % (mn, ops, addr))
    if not insns:
        res.errors.append("the object contains no instructions.")
    return res
