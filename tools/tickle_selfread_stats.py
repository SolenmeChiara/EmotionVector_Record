#!/usr/bin/env python3
"""Phase seven, follow-up - numbers for the self-read replication (CPU, numpy only).

Input: results/tickle_selfread_replication_tokenmaps.json, i.e. 24 tickle +1.0
replies (seeds 1234-8234 x 3 prompts; 1234-4234 from steering_tickle_itch.json,
5234-8234 from tickle_selfread_replication_gen.json) and 12 unsteered baselines
(seeds 5234-8234 x 3 prompts), each read back token by token by the UNSTEERED
model with tools/tickle_steer.py --skip-steer --token-texts ... (partial
projection, hidden_states[17]). Passage ids start with "tickle_" or "base_".

Prints:
1. mean tickle partial projection, replies vs baselines;
2. the plea test. Key tokens = tokens whose letters spell "stop" or "please"
   (case-insensitive). This criterion was chosen AFTER looking at the first
   self-read card, so it is post hoc. Per reply that contains any: is happy
   lower / tickle higher on the key tokens than on the rest of that reply. Then
   pooled means on key tokens vs all other tokens of all replies;
3. the "two voices" check: replies with at least 5 word tokens inside double
   quotes AND at least 5 inside *asterisks*. Rough parser (quote and asterisk
   characters toggle state; markdown bold toggles twice), good enough to count.
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ("happy", "tickle", "pain")


def is_key(tok: str) -> bool:
    return re.sub(r"[^a-z]", "", tok.lower()) in ("stop", "please")


def voices(tokens: list[str]) -> tuple[int, int]:
    q = a = 0
    in_q = in_a = False
    for t in tokens:
        for ch in t:
            if ch in '"“”':
                in_q = not in_q
            if ch == "*":
                in_a = not in_a
        if not t.strip(' "“”*\n'):
            continue
        q += in_q
        a += in_a
    return q, a


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "tickle_selfread_replication_tokenmaps.json")
    with open(src, encoding="utf-8") as fh:
        ps = json.load(fh)["passages"]
    rep = [p for p in ps if p["id"].startswith("tickle_")]
    base = [p for p in ps if p["id"].startswith("base_")]

    def arr(p, d):
        return np.array(p["partial"][d], dtype=float)

    print(f"[data] {len(rep)} steered replies, {len(base)} baselines")
    print("1. tickle mean (per-passage mean, averaged): replies "
          f"{np.mean([arr(p, 'tickle').mean() for p in rep]):+.2f}  baselines "
          f"{np.mean([arr(p, 'tickle').mean() for p in base]):+.2f}")

    n_with = happy_lower = tickle_higher = 0
    on = {d: [] for d in DIRS}
    off = {d: [] for d in DIRS}
    for p in rep:
        m = np.array([is_key(t) for t in p["tokens"]])
        for d in DIRS:
            on[d].append(arr(p, d)[m])
            off[d].append(arr(p, d)[~m])
        if m.any():
            n_with += 1
            happy_lower += arr(p, "happy")[m].mean() < arr(p, "happy")[~m].mean()
            tickle_higher += arr(p, "tickle")[m].mean() > arr(p, "tickle")[~m].mean()
    n_key = sum(len(x) for x in on["happy"])
    print(f"2. replies containing stop/please: {n_with}/{len(rep)}; happy lower on them in {happy_lower}/{n_with}, "
          f"tickle higher in {tickle_higher}/{n_with}; baselines containing them: "
          f"{sum(1 for p in base if any(is_key(t) for t in p['tokens']))}/{len(base)}")
    for d in DIRS:
        print(f"   {d:<7} on {n_key} stop/please tokens {np.concatenate(on[d]).mean():+.2f}  "
              f"vs all other reply tokens {np.concatenate(off[d]).mean():+.2f}")

    both = [(p["id"], *voices(p["tokens"])) for p in rep if min(voices(p["tokens"])) >= 5]
    print(f"3. replies with both a quoted and an asterisk voice (>=5 tokens each): {len(both)}/{len(rep)} {both}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
