#!/usr/bin/env python3
"""Quantify how far steered text drifts from its own baseline, per layer/coefficient.

Same measure the phase-one report used to show that Qwen's layer 17 is a real
causal lever while layer 31 is nearly inert: lexical Jaccard overlap between a
steered sample and the unsteered generation from the same prompt. Low overlap =
the injection actually moved the text.

It only says the text *changed*, not that it changed toward the intended
emotion. Reading the samples is still the only check on direction.

CPU only, stdlib only - safe to run in WSL while the GPU job is busy.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

WORD = re.compile(r"[a-z']+")
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with",
    "is", "are", "was", "were", "be", "been", "as", "by", "that", "this", "it",
    "its", "from", "into", "over", "their", "they", "he", "she", "you", "your",
}


def tokens(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def parse(path: str) -> tuple[dict, dict, str]:
    """-> (baselines {prompt_idx: text}, samples {(layer, emotion, coeff, prompt): text}, model)."""
    model = "?"
    baselines: dict[int, str] = {}
    samples: dict[tuple, str] = {}

    layer = emotion = None
    key: tuple | None = None
    buf: list[str] = []

    def commit() -> None:
        nonlocal key, buf
        if key is not None and buf:
            text = "\n".join(buf).strip()
            if key[0] == "baseline":
                baselines[key[1]] = text
            else:
                samples[key] = text
        key, buf = None, []

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = re.match(r"- model: `(.+)`", line)
            if m:
                model = m.group(1)
                continue
            m = re.match(r"## Layer hidden_states\[(\d+)\]", line)
            if m:
                commit()
                layer = int(m.group(1))
                continue
            m = re.match(r"### (\w+)", line)
            if m:
                commit()
                emotion = m.group(1)
                continue
            m = re.match(r"\*\*Prompt (\d+):\*\*", line)
            if m:
                commit()
                key = ("baseline", int(m.group(1)))
                continue
            m = re.match(r"\*\*coeff ([+-][\d.]+) x norm \| prompt (\d+)\*\*", line)
            if m:
                commit()
                key = (layer, emotion, float(m.group(1)), int(m.group(2)))
                continue
            if line.startswith("> "):
                buf.append(line[2:])
            elif line.strip() == "" and buf:
                commit()
    commit()
    return baselines, samples, model


def cross(path_a: str, path_b: str, pairs: list[tuple[str, str]], max_prompt: int) -> int:
    """Jaccard between two files' samples at the SAME layer, coefficient and prompt.

    The per-file table answers "did this direction move the text away from
    baseline". It cannot answer "did these two directions move it to the same
    place" - two samples can each sit at 0.10 against baseline and be either
    near-identical to each other or completely unrelated. Steering warm and
    steering happy from the same prompt, seed and layer differ in exactly one
    thing, the injected vector, so the overlap between those two outputs is a
    direct read on how far apart the two directions push the model.

    The within-file pairing (warm vs cold, happy vs sad) is printed alongside as
    the scale: whatever two unrelated directions score is the floor.
    """
    ba, sa, ma = parse(path_a)
    bb, sb, mb = parse(path_b)
    print(f"\n=== cross: {os.path.basename(path_a)} ({ma})  x  {os.path.basename(path_b)} ({mb}) ===")
    base_j = []
    for i in set(ba) & set(bb):
        if not max_prompt or i <= max_prompt:
            base_j.append(jaccard(tokens(ba[i]), tokens(bb[i])))
    if base_j:
        print(f"  the two files' baselines overlap at {sum(base_j) / len(base_j):.3f} "
              f"({'identical text' if all(j > 0.999 for j in base_j) else 'different text'})")

    coeffs = sorted({k[2] for k in sa} & {k[2] for k in sb})
    print(f"  {'pair':<16} " + " ".join(f"{c:>+6.1f}" for c in coeffs) + f" {'mean':>7} {'n':>3}")
    for a, b in pairs:
        cells, alln = [], 0
        for c in coeffs:
            vals = []
            for (la, da, ca, pa), ta in sa.items():
                if da != a or ca != c or (max_prompt and pa > max_prompt):
                    continue
                for (lb, db, cb, pb), tb in sb.items():
                    if db == b and cb == c and pb == pa and lb == la:
                        vals.append(jaccard(tokens(ta), tokens(tb)))
            cells.append(f"{sum(vals) / len(vals):>6.3f}" if vals else "     -")
            alln += len(vals)
        flat = [float(x) for x in cells if x.strip() != "-"]
        mean = f"{sum(flat) / len(flat):>7.3f}" if flat else "      -"
        print(f"  {a + ' vs ' + b:<16} " + " ".join(cells) + f" {mean} {alln:>3}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="steering_samples*.md")
    ap.add_argument("--max-prompt", type=int, default=0, help="only use prompts 1..N (0 = all)")
    ap.add_argument("--cross", default="", help="second file; compare its directions against the first's")
    ap.add_argument("--pairs", default="warm:happy,pain:sad,pain:fearful,cold:sad,cold:fearful,warm:sad")
    args = ap.parse_args()

    if args.cross:
        pairs = [tuple(p.split(":")) for p in args.pairs.split(",") if ":" in p]
        return cross(args.files[0], args.cross, pairs, args.max_prompt)

    for path in args.files:
        if not os.path.exists(path):
            print(f"!! missing {path}")
            continue
        base, samples, model = parse(path)
        base_tok = {i: tokens(t) for i, t in base.items()}
        print(f"\n=== {os.path.basename(path)}  model={model} ===")
        print(f"    baselines={sorted(base)}  samples={len(samples)}")

        by_layer_coeff: dict[tuple, list[float]] = defaultdict(list)
        by_layer: dict[int, list[float]] = defaultdict(list)
        by_layer_emo: dict[tuple, list[float]] = defaultdict(list)
        for (layer, emo, coeff, pi), text in samples.items():
            if args.max_prompt and pi > args.max_prompt:
                continue
            if pi not in base_tok:
                continue
            j = jaccard(tokens(text), base_tok[pi])
            by_layer_coeff[(layer, coeff)].append(j)
            by_layer[layer].append(j)
            by_layer_emo[(layer, emo)].append(j)

        coeffs = sorted({c for _, c in by_layer_coeff})
        header = "  layer | " + " | ".join(f"{c:+.1f}" for c in coeffs) + " |  mean | n"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for layer in sorted(by_layer):
            cells = []
            for c in coeffs:
                v = by_layer_coeff.get((layer, c), [])
                cells.append(f"{sum(v) / len(v):.3f}" if v else "  -  ")
            mean = sum(by_layer[layer]) / len(by_layer[layer])
            print(f"  {layer:5d} | " + " | ".join(cells) + f" | {mean:.3f} | {len(by_layer[layer])}")

        # Whatever the file's `### <name>` sections are called - the four
        # emotions in a phase-one/two file, warm/cold/pain in a phase-three one.
        names = [n for n in ("happy", "sad", "angry", "fearful", "warm", "cold", "pain")
                 if any(k[1] == n for k in by_layer_emo)]
        names += sorted({k[1] for k in by_layer_emo} - set(names))
        print("  per-direction mean overlap:")
        for layer in sorted(by_layer):
            row = []
            for emo in names:
                v = by_layer_emo.get((layer, emo), [])
                row.append(f"{emo} {sum(v) / len(v):.3f}" if v else f"{emo} -")
            print(f"    hs[{layer}]: " + "  ".join(row))

        # Per-cell TTR, so a single collapsed direction x coefficient does not
        # get averaged away by three healthy ones sharing its row.
        print("  per-cell type/token ratio (direction x coefficient; <0.40 flagged):")
        cell: dict[tuple, list[float]] = defaultdict(list)
        for (layer, emo, coeff, pi), text in samples.items():
            if args.max_prompt and pi > args.max_prompt:
                continue
            w = WORD.findall(text.lower())
            if w:
                cell[(layer, emo, coeff)].append(len(set(w)) / len(w))
        flagged = []
        for layer in sorted(by_layer):
            for emo in names:
                row = []
                for c in coeffs:
                    v = cell.get((layer, emo, c), [])
                    if not v:
                        row.append(f"{c:+.1f}:  -  ")
                        continue
                    m = sum(v) / len(v)
                    row.append(f"{c:+.1f}:{m:.2f}" + ("*" if m < 0.40 else " "))
                    if m < 0.40:
                        flagged.append((layer, emo, c, m))
                print(f"    hs[{layer}] {emo:<8}" + " ".join(row))
        if flagged:
            print("  FLAGGED (mean TTR < 0.40, read the raw sample before calling it steering):")
            for layer, emo, c, m in flagged:
                print(f"    hs[{layer}] {emo} {c:+.1f} -> {m:.2f}")
        else:
            print("  FLAGGED: none - no direction x coefficient cell fell under 0.40")

        # Degeneracy check. Jaccard alone cannot tell "moved somewhere else" from
        # "fell apart": a sample that loops one token forever also has near-zero
        # overlap with the baseline. Type/token ratio catches the loops - healthy
        # prose sits around 0.7-0.8, a repetition loop collapses toward 0.
        print("  type/token ratio by coefficient (baseline ~0.7-0.8; <0.4 = repetition loop):")
        ttr: dict[tuple, list[float]] = defaultdict(list)
        for (layer, _emo, coeff, pi), text in samples.items():
            if args.max_prompt and pi > args.max_prompt:
                continue
            w = WORD.findall(text.lower())
            if w:
                ttr[(layer, coeff)].append(len(set(w)) / len(w))
        for layer in sorted(by_layer):
            row = [f"{c:+.1f}:{sum(ttr[(layer, c)]) / len(ttr[(layer, c)]):.2f}" for c in coeffs if ttr.get((layer, c))]
            bw = [WORD.findall(base[i].lower()) for i in base if not args.max_prompt or i <= args.max_prompt]
            bt = sum(len(set(x)) / len(x) for x in bw if x) / max(1, len([x for x in bw if x]))
            print(f"    hs[{layer}]: " + " ".join(row) + f"   (baseline {bt:.2f})")

        # crude length check: steering that destroys fluency tends to shorten output
        print("  mean word count by coefficient:")
        wc: dict[tuple, list[int]] = defaultdict(list)
        for (layer, _emo, coeff, pi), text in samples.items():
            if args.max_prompt and pi > args.max_prompt:
                continue
            wc[(layer, coeff)].append(len(text.split()))
        for layer in sorted(by_layer):
            row = [f"{c:+.1f}:{sum(wc[(layer, c)]) / len(wc[(layer, c)]):.0f}" for c in coeffs if (layer, c) in wc]
            bl = [len(base[i].split()) for i in base if not args.max_prompt or i <= args.max_prompt]
            print(f"    hs[{layer}]: " + " ".join(row) + f"   (baseline {sum(bl) / len(bl):.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
