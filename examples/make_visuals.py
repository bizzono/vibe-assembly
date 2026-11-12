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


def capture_asm_grid(filename="standalone_mandelbrot.s"):
    """Compile examples/<filename>, run it, and parse its 24-bit ANSI pixels."""
    src = ROOT / "examples" / filename
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "asm_app"
        subprocess.run(["clang", str(src), "-o", str(exe)], check=True)
        proc = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
    rows = []
    for line in proc.stdout.splitlines():
        matches = ANSI_PAIR_RE.findall(line)
        if matches:
            rows.append([(int(r1), int(g1), int(b1), int(r2), int(g2), int(b2)) for r1, g1, b1, r2, g2, b2 in matches])
    assert len(rows) == 24 and len(rows[0]) == 72, f"unexpected grid shape: {len(rows)}x{len(rows[0]) if rows else 0}"
    return rows


def capture_mandelbrot_grid():
    return capture_asm_grid("standalone_mandelbrot.s")


def flatten_half_rows(half_rows):
    """Convert 24 half-block rows into 48 pixel rows of 72 '#rrggbb' strings."""
    pixel_rows = []
    for hr in half_rows:
        pixel_rows.append(["#%02x%02x%02x" % (r1, g1, b1) for (r1, g1, b1, _, _, _) in hr])
        pixel_rows.append(["#%02x%02x%02x" % (r2, g2, b2) for (_, _, _, r2, g2, b2) in hr])
    return pixel_rows



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


C_BENCH_SRC = r"""
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

static const uint8_t MAP[256] = {
    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
    1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1,
    1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1,
    1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
    1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1,
    1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1,
    1,2,2,0,2,2,2,0,0,2,3,3,2,0,0,1,
    1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1,
    1,0,4,0,0,4,0,0,0,3,0,0,2,0,0,1,
    1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1,
    1,0,4,0,0,4,0,0,0,2,2,2,2,0,0,1,
    1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
    1,0,0,2,3,2,0,0,4,0,0,4,0,0,0,1,
    1,0,0,2,0,2,0,0,0,0,0,0,0,0,0,1,
    1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
    1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
};

__attribute__((noinline))
double bench_doom_c(int frames) {
    double t0 = now_ms();
    volatile uint64_t acc = 0;
    double posX = 3.5, posY = 3.5, dirX = 0.84, dirY = 0.54, planeX = -0.36, planeY = 0.55;
    for (int f = 0; f < frames; f++) {
        uint64_t s = 0;
        for (int col = 0; col < 72; col++) {
            for (int row = 0; row < 48; row++) {
                double camX = 2.0 * col / 72.0 - 1.0 + 1e-9 * f;
                double rdx = dirX + planeX * camX;
                double rdy = dirY + planeY * camX;
                int mx = (int)posX, my = (int)posY;
                double ddx = fabs(1.0 / rdx), ddy = fabs(1.0 / rdy);
                int sx = rdx < 0 ? -1 : 1, sy = rdy < 0 ? -1 : 1;
                double sdx = rdx < 0 ? (posX - mx) * ddx : (mx + 1.0 - posX) * ddx;
                double sdy = rdy < 0 ? (posY - my) * ddy : (my + 1.0 - posY) * ddy;
                int side = 0, hit = 0;
                for (int step = 0; step < 32; step++) {
                    if (sdx < sdy) { sdx += ddx; mx = (mx + sx) & 15; side = 0; }
                    else { sdy += ddy; my = (my + sy) & 15; side = 1; }
                    hit = MAP[(my << 4) + mx];
                    if (hit) break;
                }
                double dist = side == 0 ? (sdx - ddx) : (sdy - ddy);
                int lh = (int)(44.0 / dist);
                int atten = (int)(256.0 / (1.0 + 0.14 * dist));
                if (row >= 24 - lh / 2 && row < 24 + lh / 2) s += (uint64_t)(hit * atten);
            }
        }
        acc += s;
    }
    return now_ms() - t0;
}

__attribute__((noinline))
double bench_snake_c(int ticks) {
    double t0 = now_ms();
    uint8_t board[864];
    memset(board, 0, sizeof(board));
    int hx = 18, hy = 12, ax = 28, ay = 7;
    uint32_t seed = 0x24681357u;
    volatile uint64_t score = 0;
    const int dx[4] = {1, -1, 0, 0};
    const int dy[4] = {0, 0, 1, -1};
    for (int t = 0; t < ticks; t++) {
        int best_d = 999, bx = hx, by = hy;
        for (int dir = 0; dir < 4; dir++) {
            int nx = hx + dx[dir], ny = hy + dy[dir];
            if (nx < 1 || nx > 34 || ny < 1 || ny > 22) continue;
            int penalty = board[ny * 36 + nx] ? 4 : 0;
            int d = abs(nx - ax) + abs(ny - ay) + penalty;
            if (d < best_d) { best_d = d; bx = nx; by = ny; }
        }
        hx = bx; hy = by;
        board[hy * 36 + hx] = (uint8_t)((t & 63) + 1);
        if (hx == ax && hy == ay) {
            score++;
            seed = seed * 1664525u + 1013904223u;
            ax = 2 + ((seed >> 16) % 32);
            ay = 2 + ((seed >> 24) % 20);
        }
    }
    return now_ms() - t0;
}

__attribute__((noinline))
double bench_nbody_c(int steps) {
    double t0 = now_ms();
    double x[64], y[64], vx[64], vy[64];
    for (int i = 0; i < 64; i++) {
        x[i] = (double)i; y[i] = 0.5 * i; vx[i] = 0.125; vy[i] = -0.125;
    }
    for (int s = 0; s < steps; s++) {
        for (int i = 0; i < 64; i++) {
            double xi = x[i], yi = y[i], vxi = vx[i], vyi = vy[i];
            for (int j = 0; j < 64; j++) {
                double dx = x[j] - xi, dy = y[j] - yi;
                double r2 = dx * dx + dy * dy + 0.25;
                double r = sqrt(r2);
                double f = 0.01 / (r2 * r);
                vxi += dx * f; vyi += dy * f;
            }
            x[i] = xi + vxi * 0.01; y[i] = yi + vyi * 0.01;
            vx[i] = vxi; vy[i] = vyi;
        }
    }
    volatile double sink = x[0] + y[0];
    (void)sink;
    return now_ms() - t0;
}

int main(void) {
    printf("%.3f %.3f %.3f\n", bench_doom_c(10000), bench_snake_c(1000000), bench_nbody_c(10000));
    return 0;
}
"""


def measure_asm_bench(filename: str) -> float:
    import time
    src = ROOT / "examples" / filename
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "asm_bench"
        subprocess.run(["clang", str(src), "-o", str(exe)], check=True)
        # Warm up
        subprocess.run([str(exe), "--bench"], capture_output=True, check=True)
        best = 1e9
        for _ in range(5):
            t0 = time.perf_counter()
            subprocess.run([str(exe), "--bench"], capture_output=True, check=True)
            dt = (time.perf_counter() - t0) * 1000.0
            if dt < best:
                best = dt
    return round(best, 2)


JS_BENCH_SRC = r"""
const { performance } = require("perf_hooks");
const MAP = new Uint8Array([
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
  1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1,
  1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1,
  1,2,2,0,2,2,2,0,0,2,3,3,2,0,0,1,
  1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1,
  1,0,4,0,0,4,0,0,0,3,0,0,2,0,0,1,
  1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1,
  1,0,4,0,0,4,0,0,0,2,2,2,2,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
  1,0,0,2,3,2,0,0,4,0,0,4,0,0,0,1,
  1,0,0,2,0,2,0,0,0,0,0,0,0,0,0,1,
  1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
]);
function benchDoom(frames) {
  const t0 = performance.now();
  let acc = 0;
  const posX = 3.5, posY = 3.5, dirX = 0.84, dirY = 0.54, planeX = -0.36, planeY = 0.55;
  for (let f = 0; f < frames; f++) {
    for (let col = 0; col < 72; col++) {
      for (let row = 0; row < 48; row++) {
        const camX = 2.0 * col / 72.0 - 1.0 + 1e-9 * f;
        const rdx = dirX + planeX * camX, rdy = dirY + planeY * camX;
        let mx = posX | 0, my = posY | 0;
        const ddx = Math.abs(1.0 / rdx), ddy = Math.abs(1.0 / rdy);
        const sx = rdx < 0 ? -1 : 1, sy = rdy < 0 ? -1 : 1;
        let sdx = rdx < 0 ? (posX - mx) * ddx : (mx + 1.0 - posX) * ddx;
        let sdy = rdy < 0 ? (posY - my) * ddy : (my + 1.0 - posY) * ddy;
        let side = 0, hit = 0;
        for (let step = 0; step < 32; step++) {
          if (sdx < sdy) { sdx += ddx; mx = (mx + sx) & 15; side = 0; }
          else { sdy += ddy; my = (my + sy) & 15; side = 1; }
          hit = MAP[(my << 4) + mx];
          if (hit) break;
        }
        const dist = side === 0 ? (sdx - ddx) : (sdy - ddy);
        const lh = (44.0 / dist) | 0;
        const atten = (256.0 / (1.0 + 0.14 * dist)) | 0;
        if (row >= 24 - (lh >> 1) && row < 24 + (lh >> 1)) acc += hit * atten;
      }
    }
  }
  if (acc === -1) console.log(acc);
  return (performance.now() - t0) * (10000 / frames);
}
function benchSnake(ticks) {
  const t0 = performance.now();
  const board = new Uint8Array(864);
  let hx = 18, hy = 12, ax = 28, ay = 7, seed = 0x24681357 >>> 0, score = 0;
  const dx = [1, -1, 0, 0], dy = [0, 0, 1, -1];
  for (let t = 0; t < ticks; t++) {
    let bestD = 999, bx = hx, by = hy;
    for (let dir = 0; dir < 4; dir++) {
      const nx = hx + dx[dir], ny = hy + dy[dir];
      if (nx < 1 || nx > 34 || ny < 1 || ny > 22) continue;
      const pen = board[ny * 36 + nx] ? 4 : 0;
      const d = Math.abs(nx - ax) + Math.abs(ny - ay) + pen;
      if (d < bestD) { bestD = d; bx = nx; by = ny; }
    }
    hx = bx; hy = by;
    board[hy * 36 + hx] = (t & 63) + 1;
    if (hx === ax && hy === ay) {
      score++;
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      ax = 2 + ((seed >>> 16) % 32);
      ay = 2 + ((seed >>> 24) % 20);
    }
  }
  if (score === -1) console.log(score);
  return performance.now() - t0;
}
function benchNbody(steps) {
  const t0 = performance.now();
  const x = new Float64Array(64), y = new Float64Array(64), vx = new Float64Array(64), vy = new Float64Array(64);
  for (let i = 0; i < 64; i++) { x[i] = i; y[i] = 0.5 * i; vx[i] = 0.125; vy[i] = -0.125; }
  for (let s = 0; s < steps; s++) {
    for (let i = 0; i < 64; i++) {
      let xi = x[i], yi = y[i], vxi = vx[i], vyi = vy[i];
      for (let j = 0; j < 64; j++) {
        const dx = x[j] - xi, dy = y[j] - yi;
        const r2 = dx * dx + dy * dy + 0.25;
        const f = 0.01 / (r2 * Math.sqrt(r2));
        vxi += dx * f; vyi += dy * f;
      }
      x[i] = xi + vxi * 0.01; y[i] = yi + vyi * 0.01; vx[i] = vxi; vy[i] = vyi;
    }
  }
  if (x[0] === -1e9) console.log(x[0]);
  return performance.now() - t0;
}
benchDoom(200); benchSnake(50000); benchNbody(500);
console.log(benchDoom(2000).toFixed(2), benchSnake(1000000).toFixed(2), benchNbody(10000).toFixed(2));
"""


def measure_py_benches():
    import math
    import time

    # 1. DOOM raycaster in Python (scaled from 50 frames -> 10,000 frames)
    mp = [
        1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
        1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1,
        1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1,
        1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
        1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1,
        1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1,
        1,2,2,0,2,2,2,0,0,2,3,3,2,0,0,1,
        1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1,
        1,0,4,0,0,4,0,0,0,3,0,0,2,0,0,1,
        1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1,
        1,0,4,0,0,4,0,0,0,2,2,2,2,0,0,1,
        1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
        1,0,0,2,3,2,0,0,4,0,0,4,0,0,0,1,
        1,0,0,2,0,2,0,0,0,0,0,0,0,0,0,1,
        1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,
        1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
    ]
    t0 = time.perf_counter()
    acc = 0
    for f in range(25):
        for col in range(72):
            for row in range(48):
                camX = 2.0 * col / 72.0 - 1.0
                rdx = 0.84 - 0.36 * camX
                rdy = 0.54 + 0.55 * camX
                mx, my = 3, 3
                ddx, ddy = abs(1.0 / rdx), abs(1.0 / rdy)
                sx = -1 if rdx < 0 else 1
                sy = -1 if rdy < 0 else 1
                sdx = (3.5 - mx) * ddx if rdx < 0 else (mx + 1.0 - 3.5) * ddx
                sdy = (3.5 - my) * ddy if rdy < 0 else (my + 1.0 - 3.5) * ddy
                side = 0
                hit = 0
                for _ in range(16):
                    if sdx < sdy:
                        sdx += ddx
                        mx = (mx + sx) & 15
                        side = 0
                    else:
                        sdy += ddy
                        my = (my + sy) & 15
                        side = 1
                    hit = mp[(my << 4) + mx]
                    if hit:
                        break
                dist = (sdx - ddx) if side == 0 else (sdy - ddy)
                lh = int(44.0 / dist)
                if 24 - (lh >> 1) <= row < 24 + (lh >> 1):
                    acc += hit
    doom_py_ms = round((time.perf_counter() - t0) * 1000.0 * (10000.0 / 25.0), 1)

    # 2. Snake AI in Python (scaled from 25,000 ticks -> 1,000,000 ticks)
    t0 = time.perf_counter()
    board = [0] * 864
    hx, hy, ax, ay = 18, 12, 28, 7
    seed = 0x24681357
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for t in range(25000):
        best_d = 999
        bx, by = hx, hy
        for dx, dy in dirs:
            nx, ny = hx + dx, hy + dy
            if 1 <= nx <= 34 and 1 <= ny <= 22:
                d = abs(nx - ax) + abs(ny - ay) + (4 if board[ny * 36 + nx] else 0)
                if d < best_d:
                    best_d, bx, by = d, nx, ny
        hx, hy = bx, by
        board[hy * 36 + hx] = (t & 63) + 1
        if hx == ax and hy == ay:
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            ax = 2 + ((seed >> 16) % 32)
            ay = 2 + ((seed >> 24) % 20)
    snake_py_ms = round((time.perf_counter() - t0) * 1000.0 * (1000000.0 / 25000.0), 1)

    # 3. N-Body in Python (scaled from 100 steps -> 10,000 steps)
    t0 = time.perf_counter()
    x = [float(i) for i in range(64)]
    y = [0.5 * i for i in range(64)]
    vx = [0.125] * 64
    vy = [-0.125] * 64
    for _ in range(100):
        for i in range(64):
            xi, yi, vxi, vyi = x[i], y[i], vx[i], vy[i]
            for j in range(64):
                dx = x[j] - xi
                dy = y[j] - yi
                r2 = dx * dx + dy * dy + 0.25
                f = 0.01 / (r2 * math.sqrt(r2))
                vxi += dx * f
                vyi += dy * f
            x[i] = xi + vxi * 0.01
            y[i] = yi + vyi * 0.01
            vx[i] = vxi
            vy[i] = vyi
    nbody_py_ms = round((time.perf_counter() - t0) * 1000.0 * (10000.0 / 100.0), 1)
    return doom_py_ms, snake_py_ms, nbody_py_ms


def build_software_benchmarks():
    doom_asm_ms = measure_asm_bench("doom_raycaster.s")
    snake_asm_ms = measure_asm_bench("snake_ai.s")
    nbody_asm_ms = measure_asm_bench("nbody_sim.s")

    with tempfile.TemporaryDirectory() as tmp:
        c_file = Path(tmp) / "bench.c"
        c_exe = Path(tmp) / "bench"
        c_file.write_text(C_BENCH_SRC)
        subprocess.run(["clang", "-O3", str(c_file), "-lm", "-o", str(c_exe)], check=True)
        out = subprocess.run([str(c_exe)], capture_output=True, text=True, check=True).stdout.strip().split()
        doom_c_ms, snake_c_ms, nbody_c_ms = [round(float(v), 2) for v in out]

        js_file = Path(tmp) / "bench.js"
        js_file.write_text(JS_BENCH_SRC)
        js_out = subprocess.run(["node", str(js_file)], capture_output=True, text=True, check=True).stdout.strip().split()
        doom_js_ms, snake_js_ms, nbody_js_ms = [round(float(v), 1) for v in js_out]

    doom_py_ms, snake_py_ms, nbody_py_ms = measure_py_benches()

    # Pull Mandelbrot 512x512 from shootout/results/results.json
    import json
    res = json.loads((ROOT / "shootout" / "results" / "results.json").read_text())
    m_ent = res["kernels"]["mandelbrot"]["entries"]
    m_asm_ms = round(m_ent["asm"]["best_ns"] / 1e6, 2)
    m_c_ms = round(m_ent["c"]["best_ns"] / 1e6, 2)
    m_js_ms = round(m_ent["js"]["best_ns"] / 1e6, 2)
    m_py_ms = round(m_ent["python"]["best_ns"] / 1e6, 1)

    apps = [
        {
            "id": "doom",
            "title": "3D DOOM / Wolf3D Raycaster",
            "subtitle": "10,000 full 3D frames (72x48 DDA + torch lighting)",
            "file": "examples/doom_raycaster.s",
            "metric": "FPS",
            "asm_ms": doom_asm_ms,
            "c_ms": doom_c_ms,
            "js_ms": doom_js_ms,
            "py_ms": doom_py_ms,
            "vs_c": round(doom_c_ms / doom_asm_ms, 2),
            "vs_py": round(doom_py_ms / doom_asm_ms, 1),
        },
        {
            "id": "snake",
            "title": "Autonomous Snake AI Engine",
            "subtitle": "1,000,000 pathfinding + collision game ticks",
            "file": "examples/snake_ai.s",
            "metric": "M ticks/s",
            "asm_ms": snake_asm_ms,
            "c_ms": snake_c_ms,
            "js_ms": snake_js_ms,
            "py_ms": snake_py_ms,
            "vs_c": round(snake_c_ms / snake_asm_ms, 2),
            "vs_py": round(snake_py_ms / snake_asm_ms, 1),
        },
        {
            "id": "nbody",
            "title": "N-Body Galaxy Collision Sim",
            "subtitle": "10,000 steps of 64-body O(N^2) gravity (40.96M pairs)",
            "file": "examples/nbody_sim.s",
            "metric": "M pairs/s",
            "asm_ms": nbody_asm_ms,
            "c_ms": nbody_c_ms,
            "js_ms": nbody_js_ms,
            "py_ms": nbody_py_ms,
            "vs_c": round(nbody_c_ms / nbody_asm_ms, 2),
            "vs_py": round(nbody_py_ms / nbody_asm_ms, 1),
        },
        {
            "id": "mandelbrot",
            "title": "Mandelbrot Fractal Renderer",
            "subtitle": "512x512 IEEE-754 grid (200 max iterations)",
            "file": "examples/standalone_mandelbrot.s",
            "metric": "FPS",
            "asm_ms": m_asm_ms,
            "c_ms": m_c_ms,
            "js_ms": m_js_ms,
            "py_ms": m_py_ms,
            "vs_c": round(m_c_ms / m_asm_ms, 2),
            "vs_py": round(m_py_ms / m_asm_ms, 1),
        },
    ]
    return apps



if __name__ == "__main__":
    grid = capture_mandelbrot_grid()
    render_standalone_mandelbrot_svg(grid)
    render_oneshot_walkthrough_svg()
