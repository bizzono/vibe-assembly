#!/usr/bin/env python3
"""Render docs/media/standalone-mandelbrot.svg and docs/media/oneshot-walkthrough.svg.

1. Compiles and runs `examples/standalone_mandelbrot.s` (100% ARM64 assembly, zero C),
   parses the actual 24-bit ANSI escape sequences it writes to stdout, and renders them
   into a crisp vector terminal showcase (`docs/media/standalone-mandelbrot.svg`).
2. Generates the One-Shot Assembly Anatomy diagram (`docs/media/oneshot-walkthrough.svg`)
   showing how a single-round NEON assembly solution works, passes the 5 verification
   gates, and links directly into a native binary.
"""
import re
import subprocess
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "docs" / "media"

ANSI_PAIR_RE = re.compile(
    r"\x1b\[38;2;(\d+);(\d+);(\d+);48;2;(\d+);(\d+);(\d+)m▀"
)


def capture_mandelbrot_grid():
    """Compile examples/standalone_mandelbrot.s, run it, and parse its 24-bit ANSI pixels."""
    src = ROOT / "examples" / "standalone_mandelbrot.s"
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "mandelbrot_app"
        subprocess.run(["clang", str(src), "-o", str(exe)], check=True)
        proc = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
    rows = []
    for line in proc.stdout.splitlines():
        matches = ANSI_PAIR_RE.findall(line)
        if matches:
            rows.append([(int(r1), int(g1), int(b1), int(r2), int(g2), int(b2)) for r1, g1, b1, r2, g2, b2 in matches])
    assert len(rows) == 24 and len(rows[0]) == 72, f"unexpected grid shape: {len(rows)}x{len(rows[0]) if rows else 0}"
    return rows


def render_standalone_mandelbrot_svg(rows):
    """Build docs/media/standalone-mandelbrot.svg from the assembly binary's output."""
    W, H = 960, 540
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        '<defs>',
        '  <style>',
        '    .mono { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }',
        '    .sans { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
        '  </style>',
        '</defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="#0d1117" stroke="#30363d" stroke-width="1.5"/>',
        # Window title bar
        '<rect x="1" y="1" width="958" height="38" rx="11" fill="#161b22"/>',
        '<line x1="1" y1="39" x2="959" y2="39" stroke="#30363d" stroke-width="1"/>',
        '<circle cx="22" cy="20" r="6" fill="#ff5f56"/>',
        '<circle cx="42" cy="20" r="6" fill="#ffbd2e"/>',
        '<circle cx="62" cy="20" r="6" fill="#27c93f"/>',
        '<text x="480" y="25" text-anchor="middle" fill="#8b949e" font-size="12.5" class="mono">'
        'examples/standalone_mandelbrot.s — 100% ARM64 assembly binary (zero C files)</text>',
        # Command prompt line
        '<text x="24" y="66" fill="#7ee787" font-size="13" class="mono">$</text>',
        '<text x="40" y="66" fill="#e6edf3" font-size="13" class="mono">'
        'clang examples/standalone_mandelbrot.s -o mandelbrot &amp;&amp; ./mandelbrot</text>',
        '<text x="24" y="90" fill="#58a6ff" font-size="12.5" font-weight="600" class="mono">'
        'vibe-assembly :: standalone ARM64 assembly Mandelbrot renderer (72x48 IEEE-754 double grid)</text>',
    ]

    # Left panel: pixel-exact rendering of the 72x48 half-block grid emitted by the assembly binary
    gx0, gy0 = 24, 106
    cell_w, cell_h = 7, 8  # each character cell is 7x16 (two 7x8 half-blocks)
    out.append(f'<rect x="{gx0 - 2}" y="{gy0 - 2}" width="{72 * cell_w + 4}" height="{48 * cell_h + 4}" '
               f'rx="4" fill="#0c0f18" stroke="#30363d" stroke-width="1"/>')

    for r_idx, row in enumerate(rows):
        y_top = gy0 + (r_idx * 2) * cell_h
        y_bot = y_top + cell_h
        for c_idx, (r1, g1, b1, r2, g2, b2) in enumerate(row):
            x = gx0 + c_idx * cell_w
            out.append(f'<rect x="{x}" y="{y_top}" width="{cell_w}" height="{cell_h}" fill="rgb({r1},{g1},{b1})"/>')
            out.append(f'<rect x="{x}" y="{y_bot}" width="{cell_w}" height="{cell_h}" fill="rgb({r2},{g2},{b2})"/>')

    out.append(f'<text x="{gx0}" y="{gy0 + 48 * cell_h + 22}" fill="#8b949e" font-size="11.5" class="mono">'
               'Output captured directly from running examples/standalone_mandelbrot.s (cardioid + period-2 bulb skip)</text>')

    # Right panel: Annotated assembly highlights + 512x512 benchmark race
    rx = 552
    out.extend([
        f'<rect x="{rx}" y="104" width="384" height="198" rx="8" fill="#161b22" stroke="#30363d"/>',
        f'<text x="{rx + 16}" y="128" fill="#f0f6fc" font-size="13" font-weight="600" class="sans">'
        'Inside the Pure-Assembly Binary</text>',
        f'<text x="{rx + 16}" y="152" fill="#79c0ff" font-size="11.5" class="mono">'
        'fmov   d2, #0.25</text>',
        f'<text x="{rx + 16}" y="170" fill="#79c0ff" font-size="11.5" class="mono">'
        'fsub   d3, d0, d2          // cr - 0.25</text>',
        f'<text x="{rx + 16}" y="188" fill="#79c0ff" font-size="11.5" class="mono">'
        'fmadd  d5, d3, d3, d4      // q = (cr-0.25)^2 + ci^2</text>',
        f'<text x="{rx + 16}" y="206" fill="#79c0ff" font-size="11.5" class="mono">'
        'fcmp   d6, d7              // cardioid skip check</text>',
        f'<text x="{rx + 16}" y="224" fill="#7ee787" font-size="11.5" class="mono">'
        'b.le   Lpoint_in_set       // skip 200-iter loop!</text>',
        f'<text x="{rx + 16}" y="248" fill="#d2a8ff" font-size="11.5" class="mono">'
        'mov    x0, #1              // stdout fd</text>',
        f'<text x="{rx + 16}" y="266" fill="#d2a8ff" font-size="11.5" class="mono">'
        'bl     _write              // single syscall flush</text>',
        f'<text x="{rx + 16}" y="288" fill="#8b949e" font-size="11" class="sans">'
        'Zero C runtime dependencies — assembles with `clang file.s`</text>',

        # Benchmark comparison box for 512x512, 200 iterations
        f'<rect x="{rx}" y="316" width="384" height="176" rx="8" fill="#161b22" stroke="#30363d"/>',
        f'<text x="{rx + 16}" y="340" fill="#f0f6fc" font-size="13" font-weight="600" class="sans">'
        '512×512 Grid (200 max iterations, bit-exact)</text>',
        f'<text x="{rx + 16}" y="358" fill="#8b949e" font-size="11" class="mono">'
        'Every entry returns exact iteration sum = 9,985,499</text>',
    ])

    bars = [
        ("ARM64 Assembly", "2.17 ms (1.0x)", 12, "#2ea043", "#7ee787"),
        ("Rust (rustc -O3)", "18.84 ms (8.7x)", 52, "#6e7681", "#e6edf3"),
        ("C (clang -O3)", "18.98 ms (8.8x)", 53, "#6e7681", "#e6edf3"),
        ("Node.js (V8 JIT)", "19.30 ms (8.9x)", 54, "#6e7681", "#e6edf3"),
        ("Python 3.15", "469.0 ms (216.6x)", 102, "#da3633", "#ff7b72"),
    ]
    for idx, (label, timing, bw, bar_col, txt_col) in enumerate(bars):
        by = 376 + idx * 22
        out.append(f'<text x="{rx + 16}" y="{by + 11}" fill="#c9d1d9" font-size="11" class="mono">{escape(label)}</text>')
        out.append(f'<rect x="{rx + 136}" y="{by + 1}" width="{bw}" height="12" rx="3" fill="{bar_col}"/>')
        out.append(f'<text x="{rx + 368}" y="{by + 11}" text-anchor="end" fill="{txt_col}" font-size="11" class="mono">{escape(timing)}</text>')

    out.append('</svg>\n')
    dest = MEDIA / "standalone-mandelbrot.svg"
    dest.write_text("\n".join(out))
    print(f"wrote {dest.relative_to(ROOT)}")


def render_oneshot_walkthrough_svg():
    """Build docs/media/oneshot-walkthrough.svg showing the 1-round lifecycle."""
    W, H = 960, 430
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        '<defs>',
        '  <style>',
        '    .mono { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }',
        '    .sans { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }',
        '  </style>',
        '</defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="#fbfaf5" stroke="#d5ceb8" stroke-width="1.5"/>',
        # Header banner
        '<rect x="1" y="1" width="958" height="48" rx="11" fill="#e5eedf"/>',
        '<line x1="1" y1="49" x2="959" y2="49" stroke="#c3d1b8" stroke-width="1"/>',
        '<text x="24" y="30" fill="#1d2b1f" font-size="13.5" font-weight="700" class="mono">'
        'ONE-SHOT ASSEMBLY WALKTHROUGH :: C PROTOTYPE TO VERIFIED KERNEL</text>',
        '<text x="936" y="30" text-anchor="end" fill="#2e6b34" font-size="12" font-weight="700" class="mono">'
        '1 ROUND · 194,840 TESTS · PASS</text>',

        # Column 1: Spec + Prompt
        '<rect x="20" y="66" width="290" height="344" rx="8" fill="#ffffff" stroke="#d5ceb8"/>',
        '<text x="36" y="92" fill="#2e6b34" font-size="11.5" font-weight="700" class="mono">1. THE CONTRACT (base64_encode)</text>',
        '<text x="36" y="116" fill="#444" font-size="12" class="sans">Give the harness a C prototype &amp; oracle:</text>',
        '<rect x="36" y="128" width="258" height="62" rx="5" fill="#f4f2ea" stroke="#e0dac6"/>',
        '<text x="46" y="148" fill="#1b1b1b" font-size="11" class="mono">size_t base64_encode(</text>',
        '<text x="46" y="164" fill="#1b1b1b" font-size="11" class="mono">    const uint8_t *src, size_t n,</text>',
        '<text x="46" y="180" fill="#1b1b1b" font-size="11" class="mono">    uint8_t *dst);</text>',

        '<text x="36" y="214" fill="#2e6b34" font-size="12" font-weight="700" class="mono">2. ONE COMMAND TO SOLVE</text>',
        '<rect x="36" y="224" width="258" height="34" rx="5" fill="#1d2420"/>',
        '<text x="46" y="246" fill="#87e093" font-size="11.5" class="mono">$ bin/vibeasm run base64_encode</text>',

        '<text x="36" y="282" fill="#444" font-size="11.5" class="sans">Solved in Round 1 (5.6 min, 21 turns):</text>',
        '<text x="36" y="304" fill="#1b1b1b" font-size="11.5" class="mono">• 24 B   :  2.97x vs clang -O3</text>',
        '<text x="36" y="322" fill="#1b1b1b" font-size="11.5" class="mono">• 255 B  :  5.27x vs clang -O3</text>',
        '<text x="36" y="340" fill="#1b1b1b" font-size="11.5" class="mono">• 4 KiB  :  5.75x vs clang -O3</text>',
        '<text x="36" y="358" fill="#1b1b1b" font-size="11.5" class="mono">• 1 MiB  :  5.84x (23.7 GB/s)</text>',
        '<text x="36" y="386" fill="#2e6b34" font-size="12.5" font-weight="700" class="mono">Geomean  :  4.79x vs clang -O3</text>',

        # Column 2: The One-Shot NEON Assembly
        '<rect x="328" y="66" width="314" height="344" rx="8" fill="#ffffff" stroke="#d5ceb8"/>',
        '<text x="344" y="92" fill="#2e6b34" font-size="12" font-weight="700" class="mono">3. WHAT THE AGENT WROTE (.s)</text>',
        '<text x="344" y="114" fill="#444" font-size="11.5" class="sans">64 Base64 chars per loop iteration, 0 branches:</text>',
        '<rect x="344" y="126" width="282" height="196" rx="5" fill="#161b22"/>',
        '<text x="354" y="146" fill="#8b949e" font-size="10" class="mono">// Load &amp; deinterleave 48 bytes (16x3)</text>',
        '<text x="354" y="162" fill="#79c0ff" font-size="10.5" class="mono">ld3  {v0.16b,v1.16b,v2.16b}, [x0], #48</text>',
        '<text x="354" y="182" fill="#8b949e" font-size="10" class="mono">// Split 24-bit triples into 6-bit lanes</text>',
        '<text x="354" y="198" fill="#d2a8ff" font-size="10.5" class="mono">ushr v3.16b, v0.16b, #2</text>',
        '<text x="354" y="214" fill="#d2a8ff" font-size="10.5" class="mono">ushr v4.16b, v1.16b, #4</text>',
        '<text x="354" y="230" fill="#d2a8ff" font-size="10.5" class="mono">sli  v4.16b, v0.16b, #4</text>',
        '<text x="354" y="250" fill="#8b949e" font-size="10" class="mono">// 64-byte alphabet lookup in 1 cycle</text>',
        '<text x="354" y="266" fill="#7ee787" font-size="10.5" class="mono">tbl  v3.16b, {v16.16b-v19.16b}, v3.16b</text>',
        '<text x="354" y="286" fill="#8b949e" font-size="10" class="mono">// Interleave &amp; store 64 Base64 bytes</text>',
        '<text x="354" y="302" fill="#ffa657" font-size="10.5" class="mono">st4  {v3.16b-v6.16b}, [x2], #64</text>',

        '<text x="344" y="344" fill="#1b1b1b" font-size="11.5" font-weight="600" class="sans">Drop directly into any C/Rust/Zig app:</text>',
        '<rect x="344" y="354" width="282" height="42" rx="5" fill="#f4f2ea" stroke="#e0dac6"/>',
        '<text x="354" y="372" fill="#1b1b1b" font-size="10.5" class="mono">$ clang -O3 app.c \\</text>',
        '<text x="354" y="388" fill="#1b1b1b" font-size="10.5" class="mono">    solutions/arm64-darwin/*.s -o app</text>',

        # Column 3: The 5 Verification Gates
        '<rect x="660" y="66" width="280" height="344" rx="8" fill="#ffffff" stroke="#d5ceb8"/>',
        '<text x="676" y="92" fill="#2e6b34" font-size="12" font-weight="700" class="mono">4. FIVE GATES BEFORE TRUST</text>',
    ]

    gates = [
        ("GATE 1 · Static Source Lint", "141 insns · no svc/brk · no .data"),
        ("GATE 2 · Object Symbol Hygiene", "Exports _base64_encode · 0 undef"),
        ("GATE 3 · ABI Register Trampoline", "x19-x29, d8-d15, sp & red zone ok"),
        ("GATE 4 · PROT_NONE Guard Pages", "1B before/after unmapped pages"),
        ("GATE 5 · Hold-Out Fuzzing", "194,840 cases (2 fresh seeds)"),
    ]
    for i, (title, desc) in enumerate(gates):
        gy = 110 + i * 56
        out.extend([
            f'<rect x="676" y="{gy}" width="248" height="46" rx="6" fill="#edf5ea" stroke="#b9d4b0"/>',
            f'<text x="688" y="{gy + 19}" fill="#1e5624" font-size="10.8" font-weight="700" class="mono">✓ {escape(title)}</text>',
            f'<text x="688" y="{gy + 35}" fill="#3d5240" font-size="9.8" class="mono">{escape(desc)}</text>',
        ])

    out.append('</svg>\n')
    dest = MEDIA / "oneshot-walkthrough.svg"
    dest.write_text("\n".join(out))
    print(f"wrote {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    grid = capture_mandelbrot_grid()
    render_standalone_mandelbrot_svg(grid)
    render_oneshot_walkthrough_svg()
