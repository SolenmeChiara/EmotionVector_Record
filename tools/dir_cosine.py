#!/usr/bin/env python3
"""Phase three step 3 - cosine geometry between sensation and emotion directions.

Both direction sets come from the same model's residual stream and are built the
same way (`d_g = mean(group) - grand mean`, unit-normalised), so their cosines are
well defined. Three things have to be reported together or the matrix is easy to
over-read:

  * **raw cosine** - what the task asked for.
  * **the shared-genre floor.** Each corpus is centred on its own grand mean, and
    both grand means contain the same neutral control plus that corpus's own
    non-neutral groups. Whatever "this passage is in SOME marked state rather
    than the flat control" looks like in the residual stream is therefore present
    in every direction on both sides, and it inflates every cell of the matrix by
    the same amount. Measuring it: `a = mean(all target groups) - grand mean`,
    one per corpus; `cos(a_sens, a_emo)` is the floor the matrix sits on.
  * **partialled cosine** - each direction with its own corpus's generic axis
    projected out, then re-normalised. This is the part of the alignment that is
    specific to *this* sensation and *this* emotion rather than shared by all of
    them.

Within-set cosines are printed too (warm vs cold, happy vs sad, ...). If warm and
cold are already at +0.8 with each other, a +0.6 against happy means much less
than it looks.

CPU + numpy only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))
from analyze import split_indices, unit


def generic_axis(acts_path: str, groups: list[str], targets: list[str], holdout: int, seed: int):
    """Per layer: unit(mean of the target groups' train acts - grand train mean).

    Recomputed from the activations with the identical split analyze.py used, so
    it lines up with the stored directions even for the phase-one files that were
    written before this quantity existed.
    """
    z = np.load(acts_path, allow_pickle=True)
    acts, labels = z["acts"], z["labels"]
    stored = [str(x) for x in z["groups"]]
    if stored != groups:
        raise SystemExit(f"{acts_path} stores groups {stored}, not {groups}")
    train, _ = split_indices(labels, holdout, seed, groups)
    tgt = np.isin(labels[train], [groups.index(t) for t in targets])
    out = np.zeros((acts.shape[0], acts.shape[2]), dtype=np.float32)
    for l in range(acts.shape[0]):
        Xtr = acts[l][train]
        out[l] = unit(Xtr[tgt].mean(0) - Xtr.mean(0))
    return out


def cos(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(a @ b / (na * nb))


def partial(d: np.ndarray, axis: np.ndarray) -> np.ndarray:
    return unit(d - axis * (d @ axis))


def table(rows: list[str], cols: list[str], fn) -> str:
    w = max(6, max(len(c) for c in cols) + 1)
    out = ["  " + " " * 9 + " ".join(f"{c:>{w}}" for c in cols)]
    for r in rows:
        out.append(f"  {r:<9}" + " ".join(f"{fn(r, c):>{w}.3f}" for c in cols))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sens-dirs", required=True)
    ap.add_argument("--sens-acts", required=True)
    ap.add_argument("--emo-dirs", required=True)
    ap.add_argument("--emo-acts", required=True)
    ap.add_argument("--layer", type=int, required=True, help="hidden_states index of the steering lever")
    ap.add_argument("--which", default="dirs_raw", choices=["dirs_raw", "dirs_denoised"])
    ap.add_argument("--holdout", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--profile", default="pain:sad,pain:fearful,warm:happy,cold:sad,cold:fearful,warm:sad")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    zs = np.load(args.sens_dirs, allow_pickle=True)
    ze = np.load(args.emo_dirs, allow_pickle=True)
    sens = [str(x) for x in zs["emotions"]]
    emos = [str(x) for x in ze["emotions"]]
    L = zs[args.which].shape[0]
    if ze[args.which].shape[0] != L:
        raise SystemExit("the two direction files have different layer counts - different models?")

    ga_s = generic_axis(args.sens_acts, sens + ["neutral"], sens, args.holdout, args.seed)
    ga_e = generic_axis(args.emo_acts, emos + ["neutral"], emos, args.holdout, args.seed)

    k = args.layer
    S = {n: zs[args.which][k, i] for i, n in enumerate(sens)}
    E = {n: ze[args.which][k, i] for i, n in enumerate(emos)}
    Sp = {n: partial(v, ga_s[k]) for n, v in S.items()}
    Ep = {n: partial(v, ga_e[k]) for n, v in E.items()}

    floor = cos(ga_s[k], ga_e[k])
    print(f"=== hidden_states[{k}]  vectors={args.which} ===")
    print(f"  sensation dirs: {os.path.basename(args.sens_dirs)}   emotion dirs: {os.path.basename(args.emo_dirs)}")
    print(f"\n  shared-genre floor  cos(generic_sens, generic_emo) = {floor:+.3f}")
    print("  (every cell of the raw matrix below carries this component)\n")

    print("  RAW cosine, sensation (rows) x emotion (cols)")
    print(table(sens, emos, lambda r, c: cos(S[r], E[c])))
    print("\n  PARTIALLED cosine (each corpus's generic axis projected out first)")
    print(table(sens, emos, lambda r, c: cos(Sp[r], Ep[c])))

    print("\n  within-set, sensation x sensation (raw / partialled)")
    print(table(sens, sens, lambda r, c: cos(S[r], S[c])))
    print(table(sens, sens, lambda r, c: cos(Sp[r], Sp[c])))
    print("\n  within-set, emotion x emotion (raw / partialled)")
    print(table(emos, emos, lambda r, c: cos(E[r], E[c])))
    print(table(emos, emos, lambda r, c: cos(Ep[r], Ep[c])))

    pairs = [tuple(p.split(":")) for p in args.profile.split(",") if p]
    pairs = [(a, b) for a, b in pairs if a in sens and b in emos]
    print(f"\n  per-layer profile of the pre-registered pairs (raw cosine), all {L} hidden states")
    print("  layer | " + " | ".join(f"{a}*{b}" for a, b in pairs))
    for l in range(L):
        Sl = {n: zs[args.which][l, i] for i, n in enumerate(sens)}
        El = {n: ze[args.which][l, i] for i, n in enumerate(emos)}
        cells = " | ".join(f"{cos(Sl[a], El[b]):+.3f}".rjust(len(f'{a}*{b}')) for a, b in pairs)
        mark = "  <- lever" if l == k else ""
        print(f"  {l:5d} | {cells}{mark}")

    if args.json_out:
        blob = {
            "layer": k,
            "which": args.which,
            "sens_dirs": args.sens_dirs,
            "emo_dirs": args.emo_dirs,
            "shared_genre_floor": floor,
            "raw": {r: {c: cos(S[r], E[c]) for c in emos} for r in sens},
            "partialled": {r: {c: cos(Sp[r], Ep[c]) for c in emos} for r in sens},
            "within_sens_raw": {r: {c: cos(S[r], S[c]) for c in sens} for r in sens},
            "within_emo_raw": {r: {c: cos(E[r], E[c]) for c in emos} for r in emos},
            "per_layer": {
                f"{a}*{b}": [cos(zs[args.which][l, sens.index(a)], ze[args.which][l, emos.index(b)]) for l in range(L)]
                for a, b in pairs
            },
        }
        with open(args.json_out, "w") as f:
            json.dump(blob, f, indent=2)
        print(f"\n-> {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
