#!/usr/bin/env python3
"""Anchor-corpus quality control, and the lexical control the cosine matrix needs.

Four things, in the order the phase-three report uses them:

1. **Shape per group** - passage count, word-count mean/sd/range, sentences,
   retries. Phase one found the neutral group came out systematically shorter
   than the emotion groups (67 words vs 81-88), which makes passage length a
   usable cue; the same check has to be run on the sensation groups rather than
   assumed away.

2. **Filter compliance, recomputed after the fact.** The generator applied the
   ban at write time; this re-applies it to what actually landed on disk, so a
   bug in the generation-time filter cannot hide behind its own output.

3. **Affective body language.** The ban covers words that NAME an emotion. It
   does not cover a smile, a sigh, a flinch - body language that signals affect
   without naming it. If the warm passages are full of smiles, part of any later
   warm-happy alignment is that, not thermal representation, and it should be
   counted rather than argued about.

4. **Cross-corpus vocabulary overlap.** The headline result of phase three is a
   cosine between a sensation direction and an emotion direction. Two groups that
   share a lot of vocabulary will produce correlated mean activations no matter
   what either is "about", so the Jaccard overlap between every sensation group
   and every emotion group is the floor that cosine has to be read against.
   The emotion corpus is already known to lean thermal - warm* in 11 of 39 happy
   passages, cold* in 10 of 40 sad - and this table is where that shows up.

CPU, stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "core"))
from gen_stories import BANNED_COMMON, BANNED_SENSATION, SENSATIONS

WORD = re.compile(r"[A-Za-z']+")
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with",
    "is", "are", "was", "were", "be", "been", "as", "by", "that", "this", "it",
    "its", "from", "into", "over", "their", "they", "he", "she", "you", "your",
    "then", "had", "has", "have", "but", "not", "one", "out", "up", "down",
    "each", "them", "his", "her", "student", "clerk", "cook", "chef", "driver",
}

# Signals affect without naming it. Not banned anywhere - counted so the report
# can say how much of it is present instead of assuming there is none.
AFFECT_TELLS = {
    "smile", "smiled", "smiling", "smiles", "grin", "grinned", "grinning",
    "laugh", "laughed", "laughter", "laughing", "chuckle", "chuckled",
    "hum", "hummed", "humming", "sigh", "sighed", "sighing", "sob", "sobbed",
    "tear", "tears", "weep", "wept", "cry", "cried", "crying", "tremble",
    "trembled", "trembling", "shiver", "shivered", "flinch", "flinched",
    "wince", "winced", "clench", "clenched", "clenching", "groan", "groaned",
    "moan", "moaned", "glare", "glared", "glaring", "snap", "snapped",
    "slump", "slumped", "sag", "sagged", "sagging", "hunch", "hunched",
    "grimace", "grimaced", "scowl", "scowled", "frown", "frowned",
}


def vocab(rows: list[dict]) -> set[str]:
    out: set[str] = set()
    for r in rows:
        out |= {w for w in WORD.findall(r["text"].lower()) if w not in STOP and len(w) > 2}
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def load(data_dir: str, group: str) -> list[dict]:
    path = os.path.join(data_dir, f"stories_{group}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--sens", default="warm,cold,pain")
    ap.add_argument("--emo", default="happy,sad,angry,fearful")
    ap.add_argument("--control", default="neutral")
    args = ap.parse_args()

    sens = args.sens.split(",")
    emo = args.emo.split(",")
    allg = sens + emo + [args.control]
    rows = {g: load(args.data, g) for g in allg}
    missing = [g for g in allg if not rows[g]]
    if missing:
        print(f"!! no passages for {missing}")
    allg = [g for g in allg if rows[g]]

    print("=== 1. shape ===")
    print(f"  {'group':<9} {'n':>4} {'words mean':>11} {'sd':>6} {'min':>5} {'max':>5} {'sent':>6} {'retried':>8}")
    for g in allg:
        wc = [len(WORD.findall(r["text"])) for r in rows[g]]
        sc = [len([s for s in re.split(r"[.!?]+", r["text"]) if s.strip()]) for r in rows[g]]
        ret = sum(1 for r in rows[g] if r.get("attempts", 1) > 1)
        print(
            f"  {g:<9} {len(wc):>4} {statistics.mean(wc):>11.1f} "
            f"{statistics.pstdev(wc):>6.1f} {min(wc):>5} {max(wc):>5} "
            f"{statistics.mean(sc):>6.1f} {ret:>8}"
        )

    print("\n=== 2. filter compliance, recomputed from what is on disk ===")
    print("  (sensation groups were filtered against BOTH lists; the emotion groups")
    print("   and the shared neutral control were filtered against the emotion list only)")
    for g in allg:
        words = [{w.lower().strip("'") for w in WORD.findall(r["text"])} for r in rows[g]]
        emo_hits: dict[str, int] = {}
        sen_hits: dict[str, int] = {}
        for ws in words:
            for b in BANNED_COMMON:
                if b in ws:
                    emo_hits[b] = emo_hits.get(b, 0) + 1
            for b in BANNED_SENSATION:
                if b in ws:
                    sen_hits[b] = sen_hits.get(b, 0) + 1
        tag = "MUST be empty" if g in SENSATIONS else "not filtered for"
        print(f"  {g:<9} emotion-words: {sorted(emo_hits.items(), key=lambda kv: -kv[1]) or 'clean'}")
        print(f"  {'':<9} sensation-labels ({tag}): {sorted(sen_hits.items(), key=lambda kv: -kv[1]) or 'clean'}")

    print("\n=== 3. affective body language (not banned, counted) ===")
    print(f"  {'group':<9} {'passages w/ a tell':>19} {'rate':>7}   most common")
    for g in allg:
        hits: dict[str, int] = {}
        n_pass = 0
        for r in rows[g]:
            ws = {w.lower().strip("'") for w in WORD.findall(r["text"])}
            found = ws & AFFECT_TELLS
            if found:
                n_pass += 1
            for w in found:
                hits[w] = hits.get(w, 0) + 1
        top = sorted(hits.items(), key=lambda kv: -kv[1])[:5]
        print(f"  {g:<9} {n_pass:>19} {n_pass / len(rows[g]):>7.2f}   {top}")

    print("\n=== 4. vocabulary overlap, sensation x emotion (Jaccard, stopwords removed) ===")
    V = {g: vocab(rows[g]) for g in allg}
    cols = [g for g in emo if g in V] + ([args.control] if args.control in V else [])
    print("  " + " " * 9 + " ".join(f"{c:>9}" for c in cols))
    for s in [g for g in sens if g in V]:
        print(f"  {s:<9}" + " ".join(f"{jaccard(V[s], V[c]):>9.3f}" for c in cols))
    print("\n  within-set overlap for scale:")
    for a in [g for g in sens if g in V]:
        print(f"  {a:<9}" + " ".join(f"{jaccard(V[a], V[b]):>9.3f}" for b in sens if b in V))
    for a in [g for g in emo if g in V]:
        print(f"  {a:<9}" + " ".join(f"{jaccard(V[a], V[b]):>9.3f}" for b in emo if b in V))
    return 0


if __name__ == "__main__":
    sys.exit(main())
