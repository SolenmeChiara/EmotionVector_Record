#!/usr/bin/env python3
"""Phase seven - draw the token-level partial projections from tickle_steer.py part 2.

One panel per passage, one line per direction (happy / pain / tickle / itch;
warm kept in the JSON and the table but not drawn, to keep four lines). Key
tokens (laughter, the plea, scratching, sting ...) get a faint vertical rule and
their text along the top, so "how does happy move at the laugh" can be read
straight off the figure. Also prints a per-passage table: whole-passage mean
per direction and the value at each key token.

Colour: a four-slot categorical palette in fixed order, checked with a palette
validator on the light surface (not included in this repo): all checks pass,
contrast WARN for slots 3-4 -> every line is direct-labelled and also has its
own dash pattern, and the numbers are printed as a table.
"""
from __future__ import annotations

import json
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#1f1f1e", "#6b6a64", "#e6e5e0"
SERIES = {  # fixed categorical order: slot 1..4
    "happy": ("#2a78d6", "-"),
    "pain": ("#eb6834", "--"),
    "tickle": ("#1baf7a", "-."),
    "itch": ("#eda100", ":"),
}
KEY = re.compile(r"^(laugh\w*|stop|please|breath\w*|gasp\w*|snort|shaking|scratch\w*|sting|feather|curled|jerked|twisted|don't|bit)$", re.IGNORECASE)


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results", "tickle_tokenmaps.json")
    out_png = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results", "tickle_token_curves.png")
    with open(src, encoding="utf-8") as f:
        blob = json.load(f)
    ps = blob["passages"]
    fig, axes = plt.subplots(len(ps), 1, figsize=(13, 3.6 * len(ps)), facecolor=SURFACE)
    if len(ps) == 1:
        axes = [axes]
    table = []
    for ax, p in zip(axes, ps):
        toks = [t.strip() for t in p["tokens"]]
        x = list(range(len(toks)))
        ax.set_facecolor(SURFACE)
        keys = [i for i, t in enumerate(toks) if KEY.match(re.sub(r"[^\w']", "", t) or "_")]
        for i in keys:
            ax.axvline(i, color=GRID, lw=1, zorder=0)
            ax.text(i, 1.02, toks[i], transform=ax.get_xaxis_transform(), rotation=60, fontsize=7.5,
                    color=MUTED, ha="left", va="bottom")
        ax.axhline(0, color=MUTED, lw=0.8, zorder=1)
        ends = []
        for name, (col, ls) in SERIES.items():
            y = p["partial"][name]
            ax.plot(x, y, color=col, lw=2, ls=ls, zorder=3, label=name)
            ends.append([y[-1], name])
        # direct labels at the line ends, pushed apart so none overlap
        lo = min(min(v) for v in p["partial"].values())
        hi = max(max(v) for v in p["partial"].values())
        gap = (hi - lo) * 0.07
        ends.sort()
        for i in range(1, len(ends)):
            ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
        for yv, name in ends:
            ax.text(len(x) + 0.5, yv, name, color=INK, fontsize=8, va="center")
        ax.set_xlim(-1, len(x) + 7)
        ax.grid(axis="y", color=GRID, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_ylabel("partial projection, hs17", color=MUTED, fontsize=8)
        ax.set_title(f"{p['id']}", loc="left", color=INK, fontsize=10, pad=34)
        ax.legend(loc="lower left", fontsize=7.5, frameon=False, ncol=4, labelcolor=INK)
        row = {"id": p["id"], "mean": {n: sum(v) / len(v) for n, v in p["partial"].items()},
               "keys": [(toks[i], {n: p["partial"][n][i] for n in p["partial"]}) for i in keys]}
        table.append(row)
    axes[-1].set_xlabel("token index", color=MUTED, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130, facecolor=SURFACE)
    print(f"-> {out_png}")
    names = list(ps[0]["partial"])
    for r in table:
        print(f"\n== {r['id']} ==  passage mean: " + "  ".join(f"{n} {r['mean'][n]:+.3f}" for n in names))
        for t, v in r["keys"]:
            print(f"   {t!r:<14}" + "  ".join(f"{n} {v[n]:+.2f}" for n in names))
    with open(os.path.splitext(out_png)[0] + "_table.json", "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
