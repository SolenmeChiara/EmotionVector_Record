#!/usr/bin/env python3
"""Phase seven - corpus QA for the tickle / itch anchors (CPU, stdlib only).

Complements tools/corpus_qa.py (shape, phase-three filters, affect tells,
Jaccard), which is run unchanged with --sens warm,cold,pain,tickle,itch. This
adds what the two new groups specifically need:

1. every ban re-applied to what is on disk (emotion + sensation labels +
   tickle/itch labels + per-group scope filter);
2. lexical families counted across ALL nine groups (share of passages that
   contain at least one word of the family). This is the table the cosines have
   to be read against: if happy is full of laughter and so is tickle, part of
   tickle.happy is the shared word;
3. exemplar imitation: share of passages that reuse any 4-gram of the worked
   exemplar shown to the generator, and the most reused 4-grams;
4. Jaccard between the two new groups and against every other group.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "core"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import gen_stories as gs
from corpus_qa import jaccard, vocab
from gen_tickle_itch import BANNED_TICKLE_ITCH, EXAMPLES, SCOPE_BAN

WORD = re.compile(r"[A-Za-z']+")
GROUPS = ["tickle", "itch", "warm", "cold", "pain", "happy", "sad", "angry", "fearful", "neutral"]

FAMILIES = {
    "laugh": r"^(laugh\w*|giggl\w*|chuckl\w*|snicker\w*|guffaw\w*|squeal\w*|cackl\w*|snort\w*)$",
    "smile": r"^(smil\w*|grin\w*|beam\w*)$",
    "breath/gasp": r"^(gasp\w*|pant\w*|wheez\w*|breathless\w*)$",
    "squirm/twist": r"^(squirm\w*|wriggl\w*|wiggl\w*|writh\w*|twist\w*|thrash\w*|flail\w*)$",
    "plea (stop/please)": r"^(stop|stopped|please|enough|mercy)$",
    "feather/brush": r"^(feather\w*|whisker\w*|brush\w*|graz\w*)$",
    "scratch/nail": r"^(scratch\w*|nail|nails|claw\w*|rub|rubbed|rubbing|rubs)$",
    "sting/raw/burn": r"^(sting\w*|stung|raw|burn\w*|smart\w*|throb\w*)$",
    "skin/red": r"^(skin|red|redden\w*|bump\w*|welt\w*)$",
    "ribs/waist/feet/armpit": r"^(rib|ribs|waist|sole|soles|armpit\w*|underarm\w*|foot|feet|toes?)$",
    "tremble/shiver": r"^(trembl\w*|shiver\w*|shak\w*|quiver\w*)$",
}


def load(group: str) -> list[dict]:
    p = os.path.join(HERE, "data", f"stories_{group}.jsonl")
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f]


def words(text: str) -> list[str]:
    return [w.lower().strip("'") for w in WORD.findall(text)]


def ngrams(ws: list[str], n: int = 4) -> set[tuple]:
    return {tuple(ws[i : i + n]) for i in range(len(ws) - n + 1)}


def main() -> int:
    rows = {g: load(g) for g in GROUPS}
    out: dict = {}

    print("=== 1. bans re-applied on disk (new groups) ===")
    for g in ("tickle", "itch"):
        banned = set(gs.BANNED_COMMON + gs.BANNED_SENSATION + BANNED_TICKLE_ITCH + SCOPE_BAN[g])
        hits = Counter(w for r in rows[g] for w in set(words(r["text"])) if w in banned)
        print(f"  {g:<7} n={len(rows[g])}  hits: {dict(hits) or 'clean'}")
        out[f"ban_hits_{g}"] = dict(hits)
    # label leakage in the OTHER corpora (not filtered for tickle/itch labels)
    for g in GROUPS[2:]:
        hits = Counter(w for r in rows[g] for w in set(words(r["text"])) if w in set(BANNED_TICKLE_ITCH))
        if hits:
            print(f"  (unfiltered) {g}: tickle/itch labels present {dict(hits)}")

    print("\n=== 2. lexical families: share of passages containing >=1 word ===")
    fam_re = {k: re.compile(v) for k, v in FAMILIES.items()}
    print("  " + f"{'family':<24}" + "".join(f"{g:>8}" for g in GROUPS))
    fam = {}
    for name, rx in fam_re.items():
        vals = {}
        for g in GROUPS:
            n = sum(1 for r in rows[g] if any(rx.match(w) for w in words(r["text"])))
            vals[g] = round(n / len(rows[g]), 2)
        fam[name] = vals
        print("  " + f"{name:<24}" + "".join(f"{vals[g]:>8.2f}" for g in GROUPS))
    out["families"] = fam

    print("\n=== 3. exemplar imitation (passages reusing any 4-gram of the exemplar) ===")
    imit = {}
    for g in ("tickle", "itch"):
        ex = ngrams(words(EXAMPLES[g]))
        c = Counter()
        n_hit = 0
        for r in rows[g]:
            shared = ngrams(words(r["text"])) & ex
            if shared:
                n_hit += 1
            c.update(shared)
        top = [(" ".join(k), v) for k, v in c.most_common(6)]
        imit[g] = {"share": round(n_hit / len(rows[g]), 2), "top": top}
        print(f"  {g:<7} {n_hit}/{len(rows[g])} passages; most reused: {top}")
    out["exemplar_imitation"] = imit

    print("\n=== 4. Jaccard (stopwords removed) ===")
    V = {g: vocab(rows[g]) for g in GROUPS}
    jac = {a: {b: round(jaccard(V[a], V[b]), 3) for b in GROUPS} for a in ("tickle", "itch")}
    print("  " + " " * 8 + "".join(f"{g:>8}" for g in GROUPS))
    for a in ("tickle", "itch"):
        print(f"  {a:<8}" + "".join(f"{jac[a][b]:>8.3f}" for b in GROUPS))
    out["jaccard"] = jac

    print("\n=== 5. shape + focus coverage ===")
    for g in ("tickle", "itch"):
        wc = [len(words(r["text"])) for r in rows[g]]
        foci = Counter(r.get("focus", "?") for r in rows[g])
        print(f"  {g:<7} n={len(wc)} words mean {sum(wc) / len(wc):.1f} min {min(wc)} max {max(wc)}; "
              f"retried {sum(1 for r in rows[g] if r['attempts'] > 1)}; foci covered {len(foci)}")
    with open(os.path.join(HERE, "results", "tickle_corpus_qa.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(f"\n-> {os.path.join(HERE, 'results', 'tickle_corpus_qa.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
