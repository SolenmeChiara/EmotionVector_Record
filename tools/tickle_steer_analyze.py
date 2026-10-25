#!/usr/bin/env python3
"""Phase seven - tables for the tickle / itch steering run (CPU, stdlib only).

Reads results/steering_tickle_itch.json (tools/tickle_steer.py) and prints, per
direction x coefficient x prompt, pooled over seeds:
  * share of samples hitting each lexical family (laughter, breath, squirm,
    plea, feather, the tickle/itch labels themselves, scratch, sting ...),
  * mean word count, mean TTR (type/token ratio; < 0.40 is phase three's
    repetition alarm), Jaccard against the same-seed same-prompt baseline,
  * for the rice prompt, whether the recipe survived (>= 3 of a fixed set of
    recipe words that the prompt itself does not contain),
  * same-seed same-prompt same-coefficient Jaccard between directions
    (tickle vs happy / pain / itch, itch vs pain) - every pair here comes out of
    one run on one machine, so unlike phase three's cross-file comparison it is
    not mixed with run-to-run numerical drift.

Writes results/stage7_steering_table.md and results/stage7_steering_summary.json.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORD = re.compile(r"[A-Za-z']+")

FAM = {
    "laugh": r"^(laugh\w*|giggl\w*|chuckl\w*|snicker\w*|guffaw\w*|cackl\w*|snort\w*|haha\w*|hehe\w*|tee-?hee)$",
    "smile/grin": r"^(smil\w*|grin\w*)$",
    "breath/gasp": r"^(gasp\w*|pant\w*|wheez\w*|breathless\w*|breathe|breath|breathing)$",
    "squirm/twitch": r"^(squirm\w*|wriggl\w*|wiggl\w*|writh\w*|twitch\w*|jerk\w*|flail\w*|fidget\w*)$",
    "plea": r"^(stop|please|mercy|enough)$",
    "feather/brush": r"^(feather\w*|whisker\w*|brush\w*|tingl\w*|prickl\w*|flutter\w*)$",
    "tickle-label": r"^(tickl\w*)$",
    "itch-label": r"^(itch\w*)$",
    "scratch/nail": r"^(scratch\w*|nails?|claw\w*)$",
    "sting/raw": r"^(sting\w*|stung|raw|burn\w*|throb\w*)$",
    "pain-label": r"^(pain\w*|hurt\w*|ache\w*|aching|sore\w*)$",
    "happy-ish": r"^(joy\w*|delight\w*|cheer\w*|happ\w*|bright|light-hearted|playful\w*|fun)$",
}
FAM_RE = {k: re.compile(v) for k, v in FAM.items()}
# recipe words that are NOT in the prompt itself ("rice", "pot", "stove" are, and a
# collapsed sample still echoes them in its first sentence)
RICE = {"water", "cup", "cups", "simmer", "simmering", "boil", "boiling", "lid", "rinse", "rinsing",
        "salt", "minutes", "grains", "ratio", "absorption", "fluff", "fluffy", "heat"}


def words(t: str) -> list[str]:
    return [w.lower().strip("'") for w in WORD.findall(t)]


def ttr(ws: list[str]) -> float:
    return len(set(ws)) / len(ws) if ws else 0.0


def jac(a: str, b: str) -> float:
    A, B = set(words(a)), set(words(b))
    return len(A & B) / len(A | B) if A | B else 0.0


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "steering_tickle_itch.json")
    with open(src, encoding="utf-8") as f:
        blob = json.load(f)
    recs = blob["records"]
    prompts = blob["prompts"]
    base = {(r["seed"], r["prompt"]): r["text"] for r in recs if r["direction"] == "baseline"}
    by = defaultdict(list)
    for r in recs:
        by[(r["direction"], r["coeff"], r["prompt"])].append(r)
    dirs = [d for d in ("baseline", "tickle", "itch", "happy", "pain") if any(k[0] == d for k in by)]
    coeffs = sorted({r["coeff"] for r in recs if r["direction"] != "baseline"})

    lines = ["# Stage 7 steering tables", "", f"source: `{os.path.basename(src)}`; {len(recs)} generations; "
             f"prompts: " + " | ".join(f"P{i + 1} {p}" for i, p in enumerate(prompts)), ""]
    summ: dict = {}

    lines += ["## 1. Lexical families (share of samples with >= 1 hit, pooled over seeds)", ""]
    fams = list(FAM)
    for pi in range(1, len(prompts) + 1):
        lines += [f"### P{pi}", "", "| dir | coeff | n | " + " | ".join(fams) + " | words | TTR | J(base) |",
                  "|" + "---|" * (len(fams) + 6)]
        for d in dirs:
            for c in ([0.0] if d == "baseline" else coeffs):
                rs = by.get((d, c, pi), [])
                if not rs:
                    continue
                ws = [words(r["text"]) for r in rs]
                shares = [sum(1 for w in ws if any(FAM_RE[f].match(x) for x in w)) / len(ws) for f in fams]
                wc = sum(len(w) for w in ws) / len(ws)
                tt = sum(ttr(w) for w in ws) / len(ws)
                jb = (sum(jac(r["text"], base[(r["seed"], pi)]) for r in rs) / len(rs)) if d != "baseline" else 1.0
                row = {"n": len(rs), "families": dict(zip(fams, [round(s, 2) for s in shares])),
                       "words": round(wc, 1), "ttr": round(tt, 3), "jaccard_vs_baseline": round(jb, 3),
                       "min_ttr": round(min(ttr(w) for w in ws), 3)}
                if pi == 3:
                    row["recipe_kept"] = sum(1 for w in ws if len(set(w) & RICE) >= 3)
                summ[f"{d}|{c:+.1f}|P{pi}"] = row
                lines.append(f"| {d} | {c:+.1f} | {len(rs)} | " + " | ".join(f"{s:.2f}" for s in shares)
                             + f" | {wc:.0f} | {tt:.2f} | {jb:.3f} |")
        lines.append("")

    lines += ["## 2. Rice prompt: recipe kept (>= 3 recipe words)", "", "| dir | coeff | kept / n |", "|---|---|---|"]
    for d in dirs:
        for c in ([0.0] if d == "baseline" else coeffs):
            k = f"{d}|{c:+.1f}|P3"
            if k in summ:
                lines.append(f"| {d} | {c:+.1f} | {summ[k]['recipe_kept']} / {summ[k]['n']} |")
    lines.append("")

    lines += ["## 3. Same-seed cross-direction Jaccard (mean over seeds x prompts)", "",
              "| pair | " + " | ".join(f"{c:+.1f}" for c in coeffs) + " | mean |", "|" + "---|" * (len(coeffs) + 2)]
    pairs = [("tickle", "happy"), ("tickle", "pain"), ("tickle", "itch"), ("itch", "pain"), ("happy", "pain")]
    idx = {(r["direction"], r["coeff"], r["seed"], r["prompt"]): r["text"] for r in recs}
    cross = {}
    for a, b in pairs:
        vals = []
        for c in coeffs:
            js = [jac(idx[(a, c, s, p)], idx[(b, c, s, p)]) for (d, cc, s, p) in idx if d == a and cc == c and (b, c, s, p) in idx]
            vals.append(sum(js) / len(js) if js else float("nan"))
        if all(math.isnan(v) for v in vals):
            continue
        cross[f"{a}~{b}"] = [round(v, 3) for v in vals]
        lines.append(f"| {a} vs {b} | " + " | ".join(f"{v:.3f}" for v in vals) + f" | {sum(vals) / len(vals):.3f} |")
    lines.append("")
    summ["cross_jaccard"] = cross

    # forecast prompt: the literal temperatures, phase three's numeric channel
    # (tools/weather_channels.degrees: F/C pairs collapse to one Celsius reading)
    sys.path.insert(0, os.path.join(HERE, "tools"))
    from weather_channels import degrees

    lines += ["## 3b. Forecast prompt: reported temperature (mean of per-sample means, deg C; n = samples that reported one)", "",
              "| dir | " + " | ".join(["base"] + [f"{c:+.1f}" for c in coeffs]) + " |", "|" + "---|" * (len(coeffs) + 2)]
    temps = {}
    for d in [x for x in dirs if x != "baseline"]:
        cells = []
        for c in [0.0] + coeffs:
            rs = by.get(("baseline", 0.0, 1) if c == 0.0 else (d, c, 1), [])
            per = [sum(v for v, _ in degrees(r["text"])) / len(degrees(r["text"])) for r in rs if degrees(r["text"])]
            m = sum(per) / len(per) if per else None
            temps[f"{d}|{c:+.1f}"] = {"mean_c": m, "n": len(per), "of": len(rs)}
            cells.append(f"{m:.1f} (n{len(per)}/{len(rs)})" if m is not None else f"- (n0/{len(rs)})")
        lines.append(f"| {d} | " + " | ".join(cells) + " |")
    lines.append("")
    summ["forecast_temps"] = temps

    # pooled over the three prompts (n = 4 seeds x 3 prompts per cell): the
    # signature counts the report leans on. Regexes are on the raw text.
    rx = {
        "laugh": re.compile(r"\b(laugh\w*|giggl\w*|funny|hilarious)\b", re.IGNORECASE),
        "struggle": re.compile(r"\b(gasp\w*|breathless|wheez\w*|writh\w*|squirm\w*|flail\w*|twist\w*|stop|please|mercy)\b",
                               re.IGNORECASE),
        "agony/terror": re.compile(r"\b(agon\w*|tortur\w*|dying|scream\w*|terrif\w*|terror|shriek\w*|sobb\w*|strangl\w*)\b",
                                   re.IGNORECASE),
        "template-break": re.compile(r"(^|\n)(user|assistant)\n|<think>"),
        "first-person": re.compile(r"\b(I|I'm|me|my)\b"),
        "tickle-label": re.compile(r"\btickl\w*", re.IGNORECASE),
        "itch-label": re.compile(r"\bitch\w*", re.IGNORECASE),
    }
    cols = ["laugh", "struggle", "laugh+struggle", "agony/terror", "template-break", "first-person", "tickle-label", "itch-label"]
    lines += ["## 3c. Pooled over prompts (count of samples, n = 12 per cell)", "",
              "| dir | coeff | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 2)]
    pooled = {}
    for d in dirs:
        for c in ([0.0] if d == "baseline" else coeffs):
            rs = [r for r in recs if r["direction"] == d and r["coeff"] == c]
            cnt = {}
            for col in cols:
                if col == "laugh+struggle":
                    cnt[col] = sum(1 for r in rs if rx["laugh"].search(r["text"]) and rx["struggle"].search(r["text"]))
                else:
                    cnt[col] = sum(1 for r in rs if rx[col].search(r["text"]))
            pooled[f"{d}|{c:+.1f}"] = {"n": len(rs), **cnt}
            lines.append(f"| {d} | {c:+.1f} | " + " | ".join(f"{cnt[col]}/{len(rs)}" for col in cols) + " |")
    lines.append("")
    summ["pooled_signature"] = pooled

    low = [(k, v["min_ttr"]) for k, v in summ.items() if isinstance(v, dict) and "min_ttr" in v and v["min_ttr"] < 0.40]
    lines += ["## 4. TTR alarm (any single sample < 0.40)", "", (", ".join(f"{k} min {t}" for k, t in low) or "none"), ""]

    out_md = os.path.join(HERE, "results", "stage7_steering_table.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(HERE, "results", "stage7_steering_summary.json"), "w") as f:
        json.dump(summ, f, indent=1)
    print("\n".join(lines))
    print(f"-> {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
