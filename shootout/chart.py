#!/usr/bin/env python3
"""Draw shootout/results/results.json as an SVG for the README.

    python3 shootout/chart.py          # writes docs/media/shootout.svg

One horizontal bar per language: how many times longer one call takes than the
assembly entry, as a geometric mean over the kernels. The scale is logarithmic and
starts at 1x (the assembly), because the values span three orders of magnitude; the
exact figures are printed at the bar ends and tabulated in RESULTS.md.

Emphasis form: the assembly entry carries the one accent hue, everything else is gray.
The picture brings its own paper-coloured surface, so it reads the same on light and
dark pages.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

PAPER, BAND, INK, SOFT, RULE = "#f3f5ec", "#d9e8d2", "#1e2622", "#5c675f", "#bccab8"
ACCENT, GRAY = "#2a78d6", "#727c75"       # validated against both paper tones (>= 3:1)
FONT = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"


def geomean(vals):
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def times(r: float) -> str:
    if r >= 100:
        return "%dx" % round(r)
    if r >= 10:
        return "%.0fx" % r
    return "%.1fx" % r


def rows_from(res: dict):
    kernels = [k for k, v in res["kernels"].items() if v["entries"].get("asm", {}).get("ok")]
    rows = []
    for lang, info in res["langs"].items():
        ratios = []
        for k in kernels:
            e = res["kernels"][k]["entries"].get(lang)
            if e and e.get("ok"):
                ratios.append(e["best_ns"] / res["kernels"][k]["entries"]["asm"]["best_ns"])
        if kernels and len(ratios) == len(kernels):
            rows.append((lang, info["name"], geomean(ratios)))
    rows.sort(key=lambda r: r[2])
    return kernels, rows


def render(res: dict) -> str:
    kernels, rows = rows_from(res)
    if not rows:
        raise SystemExit("no complete rows in results.json")
    W = 880
    row_h, top, left, right = 30, 96, 150, 96
    plot_w = W - left - right
    H = top + row_h * len(rows) + 86
    hi = max(r[2] for r in rows)
    decades = max(1, math.ceil(math.log10(hi * 1.05)))
    span = float(decades)

    def x(r: float) -> float:
        return left + plot_w * (math.log10(max(r, 1.0)) / span)

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
           'aria-labelledby="t d" font-family="%s">' % (W, H, W, H, FONT)]
    out.append('<title id="t">Time for one call compared with the agent-written assembly</title>')
    out.append('<desc id="d">%s</desc>' % escape("; ".join("%s %s" % (n, times(r)) for _, n, r in rows)))
    out.append('<rect width="%d" height="%d" fill="%s"/>' % (W, H, PAPER))
    for i in range(0, H // 60 + 1):                          # green bars, two lines each
        if i % 2 == 1:
            out.append('<rect x="0" y="%d" width="%d" height="60" fill="%s"/>' % (i * 60, W, BAND))
    out.append('<text x="28" y="40" font-size="19" font-weight="600" fill="%s">Time for one call, compared with the assembly</text>' % INK)
    out.append('<text x="28" y="64" font-size="13" fill="%s">geometric mean over %d kernels, same algorithm in every language. '
               'Shorter is faster. Log scale.</text>' % (SOFT, len(kernels)))

    ticks = []
    for d in range(decades + 1):
        for m in (1, 2, 5):
            v = m * 10 ** d
            if v <= 10 ** decades:
                ticks.append(v)
    y0, y1 = top - 8, top + row_h * len(rows) + 6
    for v in ticks:
        out.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="1"/>' % (x(v), x(v), y0, y1, RULE))
        out.append('<text x="%.1f" y="%d" font-size="12" fill="%s" text-anchor="middle">%sx</text>'
                   % (x(v), y1 + 18, SOFT, ("%d" % v)))

    for i, (lang, name, r) in enumerate(rows):
        cy = top + i * row_h + row_h / 2
        is_asm = lang == "asm"
        out.append('<text x="%d" y="%.1f" font-size="14" fill="%s" text-anchor="end" font-weight="%s">%s</text>'
                   % (left - 14, cy + 5, INK, "600" if is_asm else "400", escape(name)))
        w = max(x(r) - left, 0.0)
        if is_asm or w < 6:
            # the baseline itself: a mark, not a bar
            out.append('<rect x="%d" y="%.1f" width="5" height="18" fill="%s"/>' % (left - 2, cy - 9, ACCENT if is_asm else GRAY))
            tip = left + 10
        else:
            out.append('<path d="M %d %.1f h %.1f q 4 0 4 4 v 8 q 0 4 -4 4 h %.1f z" fill="%s"/>'
                       % (left, cy - 8, w - 4, -(w - 4), GRAY))
            tip = left + w + 8
        label = "1.0x  written by the agent, verified by the harness" if is_asm else times(r)
        out.append('<text x="%.1f" y="%.1f" font-size="13" fill="%s" font-weight="%s">%s</text>'
                   % (tip, cy + 5, INK, "600" if is_asm else "400", escape(label)))

    foot = "%s, %s. Exact times: shootout/results/RESULTS.md" % (res["host"].get("cpu", "?"), res["date"])
    out.append('<text x="28" y="%d" font-size="12" fill="%s">%s</text>' % (H - 16, SOFT, escape(foot)))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    src = HERE / "results" / "results.json"
    if not src.exists():
        print("no %s yet: run shootout/shootout.py first" % src.relative_to(ROOT), file=sys.stderr)
        return 1
    dest = ROOT / "docs" / "media" / "shootout.svg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(json.loads(src.read_text())))
    print("wrote %s" % dest.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
