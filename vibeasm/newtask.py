"""`vibeasm new`: scaffold a task that already runs end to end, ready to be edited."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from .task import SHAPES, TaskError

SPEC = """# {name}

```c
{signature}
```

TODO: say exactly what the function returns, in words a reviewer can check against
ref.c. Spell out every edge: empty input, the largest input, bytes >= 0x80, overflow.
This file and ref.c are what a human signs off on; nobody has to read the assembly.
"""

REF = {
    "bytes_to_u64": """/* {name} -- reference implementation (the oracle). Keep it plain and obviously right. */
#include <stddef.h>
#include <stdint.h>

uint64_t {name}(const uint8_t *buf, size_t len) {{
    uint64_t sum = 0; /* TODO: replace with the real thing */
    for (size_t i = 0; i < len; i++) sum += buf[i];
    return sum;
}}
""",
    "bytes_to_bytes": """/* {name} -- reference implementation (the oracle). Keep it plain and obviously right. */
#include <stddef.h>
#include <stdint.h>

/* dst has room for exactly va_out_cap(len) bytes (see gen.c). Returns bytes written. */
size_t {name}(const uint8_t *src, size_t len, uint8_t *dst) {{
    for (size_t i = 0; i < len; i++) dst[i] = (uint8_t)(src[i] ^ 0x20); /* TODO */
    return len;
}}
""",
    "ints_to_u64": """/* {name} -- reference implementation (the oracle). Keep it plain and obviously right. */
#include <stdint.h>

uint64_t {name}({params}) {{
    return {first} + 1; /* TODO: replace with the real thing */
}}
""",
}

GEN_BYTES = """/* {name} -- input generators. Flavor 0 is the typical input (benchmarks use it);
 * add adversarial flavors: the inputs most likely to break a clever implementation. */
#include "va_kit.h"

static const char *names[] = {{"random", "zeros", "ones", "text"}};

unsigned va_flavors(void) {{ return 4; }}
const char *va_flavor_name(unsigned f) {{ return names[f]; }}
{out_cap}
void va_gen(va_rng *r, uint8_t *buf, size_t len, unsigned flavor) {{
    switch (flavor) {{
    case 0: va_fill_random(r, buf, len); break;
    case 1: memset(buf, 0x00, len); break;
    case 2: memset(buf, 0xFF, len); break;
    default:
        for (size_t i = 0; i < len; i++) buf[i] = (uint8_t)(' ' + va_below(r, 95));
        break;
    }}
}}
"""

GEN_INTS = """/* {name} -- argument generators. Keep arguments small enough that the reference
 * answers in well under a millisecond: the fuzzer calls it thousands of times. */
#include "va_kit.h"

static const char *names[] = {{"small", "edges"}};

unsigned va_flavors(void) {{ return 2; }}
const char *va_flavor_name(unsigned f) {{ return names[f]; }}

void va_gen_args(va_rng *r, uint64_t a[4], unsigned flavor) {{
    for (int i = 0; i < {nargs}; i++)
        a[i] = flavor == 0 ? va_range(r, 0, 1000) : va_range(r, 0, 3); /* TODO */
}}
"""


def scaffold(root: Path, name: str, shape: str, args: List[str]) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", name):
        raise TaskError("task names are lowercase C identifiers (letters, digits, underscore)")
    if shape not in SHAPES:
        raise TaskError("--shape must be one of: %s" % ", ".join(SHAPES))
    d = root / "tasks" / name
    if d.exists():
        raise TaskError("%s already exists" % d)
    cfg = {"name": name, "symbol": name, "shape": shape, "summary": "TODO: one line", "goal_speedup": 2.0}
    if shape == "ints_to_u64":
        args = args or ["n"]
        if not 1 <= len(args) <= 4:
            raise TaskError("ints_to_u64 takes 1 to 4 arguments")
        cfg["args"] = args
        cfg["bench"] = [{"name": "typical", "args": [100] * len(args)}]
        signature = "uint64_t %s(%s);" % (name, ", ".join("uint64_t " + a for a in args))
        ref = REF[shape].format(name=name, params=", ".join("uint64_t " + a for a in args), first=args[0])
        gen = GEN_INTS.format(name=name, nargs=len(args))
    else:
        cfg["bench"] = [{"name": "16 B", "size": 16}, {"name": "256 B", "size": 256},
                        {"name": "4 KiB", "size": 4096}, {"name": "1 MiB", "size": 1048576}]
        signature = ("uint64_t %s(const uint8_t *buf, size_t len);" if shape == "bytes_to_u64"
                     else "size_t %s(const uint8_t *src, size_t len, uint8_t *dst);") % name
        ref = REF[shape].format(name=name)
        out_cap = "\nsize_t va_out_cap(size_t len) { return len; } /* TODO: exact output capacity */\n" \
            if shape == "bytes_to_bytes" else ""
        gen = GEN_BYTES.format(name=name, out_cap=out_cap)
    d.mkdir(parents=True)
    (d / "task.json").write_text(json.dumps(cfg, indent=2) + "\n")
    (d / "SPEC.md").write_text(SPEC.format(name=name, signature=signature))
    (d / "ref.c").write_text(ref)
    (d / "gen.c").write_text(gen)
    return d
