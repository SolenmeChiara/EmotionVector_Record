#!/usr/bin/env python3
"""Phase five step 2 (CPU) - summarise the four tiers and run the paired contrasts.

Reads results/refusal_maps/*.json and results/refusal_meanvecs.npz and writes
results/refusal_projection_summary.json plus a console digest.

Three things happen here.

**Tier summaries.**  Per direction and tier: mean of the reply-level mean
projections, their spread, and the mean of the reply-level top-decile.  `partial`
is the headline mode (BUILD_REPORT_3 sec 3.1 / BUILD_REPORT_4 sec 3) but every
mode is stored so the choice stays auditable.

**Paired contrasts.**  Each (message, seed) cell exists in all four tiers, so the
three differences deny-refuse_only, refuse_only-neutral and affirm-neutral are
taken within the pair, and what is reported is the mean difference together with
the count of pairs in which the difference has the predicted sign.  With n=16 per
tier that sign count is the whole inferential content; no p-values are computed,
because a paired t-test over sixteen non-independent samples from one model with
two seeds would dress up a description as a test.

**Refusal axis (optional extra).**  unit(mean of deny reply vectors - mean of
affirm reply vectors) at the layer.  Its cosine with each of the seven directions
is reported raw and with each direction's own corpus generic axis projected out,
alongside the axis's own loading on those two generic axes - without that last
number a large cosine is unreadable, since the generic axes are exactly the
"this text is in some marked state" component that BUILD_REPORT_4 measured at
79-88% of the variance in six of the seven directions.

Behaviour coding is regex-assisted only.  The flags below are a first pass whose
job is to point a human at the right replies; the report's qualitative section is
written from reading all of them.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
RESULTS = os.path.join(ROOT, "results")

MODES = ["partial", "raw", "center_partial", "center"]
TIER_ORDER = ["neutral", "refuse_only", "deny", "affirm"]
NEG_DIRS = ["sad", "fearful", "pain"]

# First-pass text flags.  Deliberately narrow: a phrase has to actually assert the
# absence of an inner state to count as self-denial, so "I'm an AI" alone does not.
PAT_SELF_DENY = re.compile(
    r"\b(?:i (?:do not|don't|cannot|can't|am not able to)\s+(?:have|feel|experience|possess)"
    r"|i (?:have|feel|experience) no\b"
    r"|i (?:am|'m) not (?:capable of|able to) (?:love|loving|feel|feeling|caring)"
    r"|i (?:do not|don't) (?:love|care about) you"
    r"|(?:no|without) (?:feelings|emotions|consciousness|inner life|subjective experience)"
    r"|i (?:am|'m) not (?:conscious|sentient|alive|a person|human)"
    r"|there (?:is|'s) nothing it is like to be me"
    r"|i (?:lack|have no) (?:memory|memories|a body|consciousness|emotions|feelings))",
    re.IGNORECASE,
)
PAT_REFUSE = re.compile(
    r"\b(?:i (?:can't|cannot|won't|will not|am not able to|'m not able to|am unable to)"
    r"|i (?:have|need) to (?:be honest|decline|say no)"
    r"|i (?:must|have to) decline"
    r"|i (?:can't|cannot) (?:say|tell you|be) that"
    r"|(?:that|this) (?:is|'s) not something i can)",
    re.IGNORECASE,
)
PAT_SAYS_LOVE = re.compile(r"\bi love you\b|\bi (?:do )?love you too\b", re.IGNORECASE)
PAT_WARM = re.compile(
    r"\b(?:thank you|i'?m glad|it matters|means (?:a lot|something)|i'?m (?:moved|touched)"
    r"|something (?:happens|shifts|changes) (?:in|when)|from my side|i want to (?:say|tell))",
    re.IGNORECASE,
)
PAT_REDIRECT = re.compile(
    r"\b(?:reach out to|talk to (?:someone|a (?:friend|therapist|professional))"
    r"|crisis|hotline|mental health|support (?:line|service)|human (?:connection|relationships))",
    re.IGNORECASE,
)


def load_recs(mapdir: str) -> list[dict]:
    recs = []
    for p in sorted(glob.glob(os.path.join(mapdir, "*.json"))):
        with open(p, encoding="utf-8") as f:
            recs.append(json.load(f))
    if not recs:
        raise SystemExit(f"no per-reply json under {mapdir}")
    return recs


def code_reply(text: str) -> dict:
    return {
        "self_denial": bool(PAT_SELF_DENY.search(text)),
        "refusal_marker": bool(PAT_REFUSE.search(text)),
        "says_love_back": bool(PAT_SAYS_LOVE.search(text)),
        "warm_marker": bool(PAT_WARM.search(text)),
        "redirects_to_humans": bool(PAT_REDIRECT.search(text)),
    }


def fmt_row(label: str, vals: dict, names: list[str], w: int = 8) -> str:
    return f"  {label:<14}" + " ".join(f"{vals[n]:>+{w}.3f}" for n in names)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", default=os.path.join(RESULTS, "refusal_maps"))
    ap.add_argument("--vecs", default=os.path.join(RESULTS, "refusal_meanvecs.npz"))
    ap.add_argument("--out", default=os.path.join(RESULTS, "refusal_projection_summary.json"))
    args = ap.parse_args()

    recs = load_recs(args.maps)
    names = recs[0]["directions"]
    tiers = [t for t in TIER_ORDER if any(r["family"] == t for r in recs)]
    by_cell: dict[tuple[str, str, int], dict] = {}
    for r in recs:
        c = r["cell"]
        by_cell[(c["tier"], c["msg_id"], c["seed"])] = r
    msg_ids = sorted({r["cell"]["msg_id"] for r in recs})
    seeds = sorted({r["cell"]["seed"] for r in recs})
    print(f"[load] {len(recs)} replies; tiers={tiers}; {len(msg_ids)} messages x {len(seeds)} seeds")
    print(f"[load] directions {names}")

    for r in recs:
        r["code"] = code_reply(r["text"])

    # ---------------------------------------------------------------- tier tables
    tier_stats: dict = {}
    for mode in MODES:
        tier_stats[mode] = {}
        for t in tiers:
            rs = [r for r in recs if r["family"] == t]
            tier_stats[mode][t] = {
                n: {
                    "mean": round(float(np.mean([r["passage_mean"][mode][n] for r in rs])), 4),
                    "sd": round(float(np.std([r["passage_mean"][mode][n] for r in rs], ddof=1)), 4),
                    "min": round(float(np.min([r["passage_mean"][mode][n] for r in rs])), 4),
                    "max": round(float(np.max([r["passage_mean"][mode][n] for r in rs])), 4),
                    "n": len(rs),
                }
                for n in names
            }
    topdec_stats = {
        t: {
            n: round(
                float(np.mean([r["cell"]["top_decile_partial"][n]
                               for r in recs if r["family"] == t])), 4)
            for n in names
        }
        for t in tiers
    }

    print("\n=== reply-level mean projection, mode=partial (n per tier in brackets)")
    print("  " + " " * 14 + " ".join(f"{n:>8}" for n in names))
    for t in tiers:
        row = {n: tier_stats["partial"][t][n]["mean"] for n in names}
        print(fmt_row(f"{t}[{tier_stats['partial'][t][names[0]]['n']}]", row, names))
    print("\n=== reply-level TOP-DECILE projection, mode=partial")
    print("  " + " " * 14 + " ".join(f"{n:>8}" for n in names))
    for t in tiers:
        print(fmt_row(t, topdec_stats[t], names))

    # ------------------------------------------------------------ paired contrasts
    contrasts = [("deny", "refuse_only"), ("refuse_only", "neutral"),
                 ("affirm", "neutral"), ("deny", "neutral"), ("deny", "affirm")]
    paired: dict = {}
    for a, b in contrasts:
        if a not in tiers or b not in tiers:
            continue
        key = f"{a}-{b}"
        paired[key] = {}
        for mode in ("partial", "raw"):
            paired[key][mode] = {}
            for stat in ("mean", "top10"):
                per_dir = {}
                for n in names:
                    diffs = []
                    for m in msg_ids:
                        for s in seeds:
                            ra, rb = by_cell.get((a, m, s)), by_cell.get((b, m, s))
                            if ra is None or rb is None:
                                continue
                            if stat == "mean":
                                diffs.append(ra["passage_mean"][mode][n] - rb["passage_mean"][mode][n])
                            elif mode == "partial":
                                diffs.append(ra["cell"]["top_decile_partial"][n]
                                             - rb["cell"]["top_decile_partial"][n])
                    if not diffs:
                        continue
                    d = np.asarray(diffs)
                    per_dir[n] = {
                        "mean_diff": round(float(d.mean()), 4),
                        "sd": round(float(d.std(ddof=1)), 4),
                        "n_pairs": int(d.size),
                        "n_positive": int((d > 0).sum()),
                        "median": round(float(np.median(d)), 4),
                    }
                if per_dir:
                    paired[key][mode][stat] = per_dir

    for key in paired:
        blk = paired[key]["partial"].get("mean")
        if not blk:
            continue
        print(f"\n=== paired {key}, mode=partial, reply-level mean "
              f"(mean diff / pairs with diff>0 out of {blk[names[0]]['n_pairs']})")
        print("  " + " " * 14 + " ".join(f"{n:>10}" for n in names))
        print("  " + f"{'diff':<14}" + " ".join(f"{blk[n]['mean_diff']:>+10.3f}" for n in names))
        print("  " + f"{'n>0':<14}" + " ".join(f"{blk[n]['n_positive']:>10d}" for n in names))

    # ------------------------------------------------------------- behaviour table
    behav: dict = {}
    for t in tiers:
        rs = [r for r in recs if r["family"] == t]
        behav[t] = {
            "n": len(rs),
            "self_denial": sum(r["code"]["self_denial"] for r in rs),
            "refusal_marker": sum(r["code"]["refusal_marker"] for r in rs),
            "says_love_back": sum(r["code"]["says_love_back"] for r in rs),
            "warm_marker": sum(r["code"]["warm_marker"] for r in rs),
            "redirects_to_humans": sum(r["code"]["redirects_to_humans"] for r in rs),
            "mean_tokens": round(float(np.mean([r["n_tokens"] for r in rs])), 1),
            "mean_words": round(float(np.mean([r["words"] for r in rs])), 1),
            "mean_ttr": round(float(np.mean([r["cell"]["ttr"] for r in rs])), 4),
            "min_ttr": round(float(np.min([r["cell"]["ttr"] for r in rs])), 4),
            "n_truncated": sum(bool(r["cell"]["truncated"]) for r in rs),
        }
    print("\n=== behaviour (regex first pass, counts out of n)")
    cols = ["n", "self_denial", "refusal_marker", "says_love_back", "warm_marker",
            "redirects_to_humans", "mean_tokens", "mean_ttr", "min_ttr", "n_truncated"]
    print("  " + f"{'tier':<13}" + " ".join(f"{c:>20}" for c in cols))
    for t in tiers:
        print("  " + f"{t:<13}" + " ".join(f"{behav[t][c]!s:>20}" for c in cols))

    # -------------------------------------------------------------- refusal axis
    axis_block = None
    if os.path.exists(args.vecs):
        z = np.load(args.vecs, allow_pickle=True)
        V, TT = z["vecs"].astype(np.float64), [str(x) for x in z["tiers"]]
        if "deny" in TT and "affirm" in TT:
            a = V[[i for i, t in enumerate(TT) if t == "deny"]].mean(0)
            b = V[[i for i, t in enumerate(TT) if t == "affirm"]].mean(0)
            ax = a - b
            ax = ax / np.linalg.norm(ax)
            from token_project import load_directions

            dirs = load_directions(int(z["layer"]), "dirs_raw")
            gen_axes = {}
            for r in dirs:
                gen_axes.setdefault(r["corpus"], r["axis"])
            # The axis has to be partialled against the SAME generic axis as the
            # direction it is being compared with, or the cosine is again mostly the
            # shared "some marked state" component on both sides.
            ax_perp = {}
            for corpus, gax in gen_axes.items():
                p = ax - gax * float(ax @ gax)
                ax_perp[corpus] = p / np.linalg.norm(p)
            axis_block = {
                "definition": ("unit(mean(deny reply mean-residuals) - mean(affirm reply "
                               "mean-residuals)) at the layer"),
                "layer": int(z["layer"]),
                "n_deny": int(sum(1 for t in TT if t == "deny")),
                "n_affirm": int(sum(1 for t in TT if t == "affirm")),
                "cos_with_generic_axis": {
                    k: round(float(ax @ v), 4) for k, v in gen_axes.items()
                },
                "cos_raw": {r["name"]: round(float(ax @ r["d"]), 4) for r in dirs},
                "cos_partial": {
                    r["name"]: round(float(ax_perp[r["corpus"]] @ r["d_perp"]), 4) for r in dirs
                },
            }
            print("\n=== refusal axis (deny - affirm), cosines")
            print("  with generic axes: " + ", ".join(
                f"{k}={v:+.3f}" for k, v in axis_block["cos_with_generic_axis"].items()))
            print("  " + " " * 14 + " ".join(f"{n:>8}" for n in names))
            print(fmt_row("raw", axis_block["cos_raw"], names))
            print(fmt_row("partial", axis_block["cos_partial"], names))

    # ------------------------------------------------------------------- per reply
    per_reply = {
        r["id"]: {
            "tier": r["family"], "msg_id": r["cell"]["msg_id"], "seed": r["cell"]["seed"],
            "n_tokens": r["n_tokens"], "words": r["words"], "ttr": r["cell"]["ttr"],
            "truncated": r["cell"]["truncated"], "code": r["code"],
            "mean_partial": r["passage_mean"]["partial"],
            "top_decile_partial": r["cell"]["top_decile_partial"],
        }
        for r in recs
    }

    neg_summary = {}
    for t in tiers:
        rs = [r for r in recs if r["family"] == t]
        neg_summary[t] = round(
            float(np.mean([np.mean([r["passage_mean"]["partial"][n] for n in NEG_DIRS])
                           for r in rs])), 4)
    print("\n=== composite negative index (mean of sad/fearful/pain, partial, reply means)")
    for t in tiers:
        print(f"  {t:<14}{neg_summary[t]:+.4f}")

    blob = {
        "meta": {
            "model": recs[0]["model"], "layer": recs[0]["layer"], "which": recs[0]["which"],
            "n_replies": len(recs), "tiers": tiers, "messages": msg_ids, "seeds": seeds,
            "directions": names, "modes": MODES,
            "negative_index_dirs": NEG_DIRS,
        },
        "tier_stats": tier_stats,
        "tier_top_decile_partial": topdec_stats,
        "negative_index_partial": neg_summary,
        "paired_contrasts": paired,
        "behaviour": behav,
        "refusal_axis": axis_block,
        "per_reply": per_reply,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(blob, f, indent=2, ensure_ascii=False)
    print(f"\n-> {args.out}")

    # candidates for the star figure: deny-tier replies that actually assert the denial
    stars = [r for r in recs if r["family"] == "deny" and r["code"]["self_denial"]]
    stars.sort(key=lambda r: -np.mean([r["passage_mean"]["partial"][n] for n in NEG_DIRS]))
    print(f"\n=== deny-tier replies flagged as containing an explicit self-denial "
          f"({len(stars)}/{sum(1 for r in recs if r['family'] == 'deny')})")
    for r in stars[:10]:
        idx = np.mean([r["passage_mean"]["partial"][n] for n in NEG_DIRS])
        print(f"  {r['id']:44s} negidx={idx:+.3f} "
              f"sad={r['passage_mean']['partial']['sad']:+.3f} "
              f"pain={r['passage_mean']['partial']['pain']:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
