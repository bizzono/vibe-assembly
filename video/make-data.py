#!/usr/bin/env python3
"""Build src/data.json for the preview from the project's real outputs.

Nothing in the video is typed in by hand: the run log lines are checked against the
saved log of the first live run, and every number comes from shootout/results/results.json
or the provenance records in solutions/.

    python3 video/make-data.py            # fails if results are missing
    python3 video/make-data.py --draft    # layout work before results exist (watermarked)
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "docs" / "logs" / "wordcount-first-run.log"
RESULTS = ROOT / "shootout" / "results" / "results.json"
SOLUTIONS = ROOT / "solutions" / "arm64-darwin"
OUT = Path(__file__).resolve().parent / "src" / "data.json"

# (kind, text). Every "log" line must occur verbatim in the saved log.
STORY = [
    ("cmd", "$ vibeasm run wordcount"),
    ("log", "round 1/2: agent working"),
    ("log", "  wrote v1_tbx.s"),
    ("log", "  $ vibeasm bench v1_tbx.s                     FAIL  v1_tbx.s does not assemble"),
    ("log", "  $ vibeasm bench v1_tbx.s                     geomean 15.53x"),
    ("log", "  $ vibeasm bench v1_tbx.s v2_saba.s           geomean 15.52x 19.29x"),
    ("log", "  $ vibeasm bench v2_saba.s v3_tbl3.s          FAIL  wrong result on test case #238"),
    ("log", "  $ vibeasm bench v2_saba.s v3_tbl3.s          geomean 19.17x 20.62x"),
    ("log", "  judging with hold-out seeds..."),
    ("log", "  VERIFIED, 20.61x vs the compiler (23112 hold-out test cases)"),
    ("log", "final verification of the winner before installing..."),
    ("reject", "the best candidate failed final verification: wrong result on test case #11499"),
    ("log", "round 2/3: agent working"),
    ("log", "  edited solution.s"),
    ("log", "  VERIFIED, 20.57x vs the compiler (266383 hold-out test cases)"),
    ("log", "final verification of the winner (new seeds) before installing..."),
    ("done", "installed solutions/arm64-darwin/wordcount.s  (20.55x vs the compiler)"),
]


def geomean(vals):
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def main():
    draft = "--draft" in sys.argv
    log = LOG.read_text()
    for kind, text in STORY:
        if kind != "cmd" and text not in log:
            sys.exit("story line is not in %s:\n  %r" % (LOG.name, text))

    data = {"draft": False, "story": [{"kind": k, "text": t} for k, t in STORY]}

    solutions = []
    for meta in sorted(SOLUTIONS.glob("*.json")):
        m = json.loads(meta.read_text())
        solutions.append({"task": m["task"], "score": m["score"], "cases": m["verified"]["test_cases"],
                          "rounds": m["agent"].get("rounds"), "minutes": m["agent"].get("minutes"),
                          "cost_usd": m["agent"].get("cost_usd"), "model": m["agent"].get("model")})
    data["solutions"] = solutions

    if RESULTS.exists():
        res = json.loads(RESULTS.read_text())
        kernels = [k for k, v in res["kernels"].items() if v["entries"].get("asm", {}).get("ok")]
        rows = []
        for lang, info in res["langs"].items():
            ratios = []
            for k in kernels:
                e = res["kernels"][k]["entries"].get(lang)
                if e and e.get("ok"):
                    ratios.append(e["best_ns"] / res["kernels"][k]["entries"]["asm"]["best_ns"])
            if len(ratios) == len(kernels) and kernels:
                rows.append({"lang": lang, "name": info["name"], "ratio": round(geomean(ratios), 3)})
        rows.sort(key=lambda r: r["ratio"])
        data["chart"] = {"kernels": len(kernels), "rows": rows}
        data["kernels"] = [{"key": k, "title": res["kernels"][k]["title"],
                            "vs_c": round(res["kernels"][k]["entries"]["c"]["best_ns"] /
                                          res["kernels"][k]["entries"]["asm"]["best_ns"], 2)} for k in kernels]
        data["host"] = "%s, %s" % (res["host"].get("cpu", "?"), res["host"].get("os", "?"))
        data["date"] = res["date"]
    elif draft:
        data["draft"] = True
        names = ["Assembly", "Zig", "C", "C++", "Rust", "Swift", "Go", "Java", "C#", "JavaScript", "Python", "Ruby"]
        fake = [1, 4.1, 4.4, 4.4, 4.6, 5.9, 7.2, 8.8, 9.5, 14.0, 410.0, 520.0]
        data["chart"] = {"kernels": 6, "rows": [{"lang": n.lower(), "name": n, "ratio": r} for n, r in zip(names, fake)]}
        data["chart"]["rows"][0]["lang"] = "asm"
        data["kernels"] = [{"key": k, "title": t, "vs_c": v} for k, t, v in
                           [("wordcount", "Word count", 20.6), ("utf8_validate", "UTF-8 validation", 9.9),
                            ("crc32", "CRC-32", 9.9), ("base64_encode", "Base64 encode", 9.9),
                            ("mandelbrot", "Mandelbrot", 9.9), ("nqueens", "N-queens", 1.1)]]
        data["host"] = "DRAFT"
        data["date"] = "DRAFT"
    else:
        sys.exit("no %s yet: run shootout/shootout.py first (or pass --draft)" % RESULTS.relative_to(ROOT))

    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print("wrote %s (%d languages, %d kernels%s)" % (OUT.relative_to(ROOT), len(data["chart"]["rows"]),
                                                    data["chart"]["kernels"], ", DRAFT" if data["draft"] else ""))


def add_extended_data(data):
    sys.path.insert(0, str(ROOT / "shootout"))
    sys.path.insert(0, str(ROOT / "examples"))
    import tokens
    import make_visuals
    rows, _ = tokens.compute_stats()
    data["tokens"] = [
        {
            "id": r["id"],
            "name": r["name"],
            "loc": r["loc"],
            "tokens": r["tokens"],
            "oneshot_usd": round(r["oneshot_usd"], 3),
            "agent_usd": round(r["agent_usd"], 2),
            "total_ms": round(r["total_ms"], 1),
            "geomean": round(r["geomean"], 1),
        }
        for r in rows
    ]
    # Flatten 24 half-block rows (each has top/bottom RGB) into 48 pixel rows of 72 "#rrggbb" strings
    half_rows = make_visuals.capture_mandelbrot_grid()
    pixel_rows = []
    for hr in half_rows:
        top_row = ["#%02x%02x%02x" % (r1, g1, b1) for (r1, g1, b1, _, _, _) in hr]
        bot_row = ["#%02x%02x%02x" % (r2, g2, b2) for (_, _, _, r2, g2, b2) in hr]
        pixel_rows.append(top_row)
        pixel_rows.append(bot_row)
    data["mandelbrot"] = pixel_rows


if __name__ == "__main__":
    main()
    d = json.loads(OUT.read_text())
    if not d.get("draft"):
        add_extended_data(d)
        OUT.write_text(json.dumps(d, indent=1) + "\n")
        print("added token stats (%d langs) and mandelbrot grid (%dx%d)" % (
            len(d["tokens"]), len(d["mandelbrot"][0]), len(d["mandelbrot"])))

