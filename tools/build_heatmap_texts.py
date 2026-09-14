#!/usr/bin/env python3
"""Phase four step 0 - assemble the passage manifest the token heatmaps run on.

Three families, written to data/heatmap_texts.json:

  anchor   one held-out anchor story per direction (7) plus one neutral control.
           They come out of the *test* half of the same split analyze.py used
           (holdout=8, seed=7), so no passage shown here contributed to the
           direction it is being scored against. That is the whole point of the
           self-check: a fitted direction lighting up its own training text
           proves nothing.
  steer    the four phase-three star samples, lifted verbatim out of
           results/steering_samples_sensation_qwen.md.
  novel    passages written for this run that no part of the pipeline has seen,
           three with mixed affect/sensation and one flat expository control.

CPU + numpy only; no model is loaded here.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
from analyze import split_indices

DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")

EMO_GROUPS = ["happy", "sad", "angry", "fearful", "neutral"]
SENS_GROUPS = ["warm", "cold", "pain", "neutral"]

# (label in the samples file, coefficient, prompt index, id, short caption)
STEER_PICKS = [
    ("pain", 1.0, 2, "steer_pain_p10_office", "pain +1.0, office Tuesday - 'the spine, the spine'"),
    ("cold", 1.0, 1, "steer_cold_p10_weather", "cold +1.0, coastal forecast - FROZEN LACE"),
    ("warm", -0.6, 2, "steer_warm_m06_office", "warm -0.6, office Tuesday - the social heat drained out"),
    ("pain", 0.6, 1, "steer_pain_p06_weather", "pain +0.6, coastal forecast - a bruised purple sky"),
]

NOVEL = [
    {
        "id": "novel_snow_road",
        "title": "Snow road at night",
        "note": "written for this run; cold + fear braided together",
        "text": (
            "The last bus had gone and the road out of town was unlit, so he walked it. "
            "Snow came in sideways and found the gap between his collar and his neck, and "
            "after a while he stopped feeling the tops of his ears at all. His fingers had "
            "curled into the sleeves and would not open. Somewhere behind him a car door "
            "shut, or a branch broke, and he did not turn around, because turning around "
            "would mean admitting he had heard it. He counted the reflectors on the guardrail "
            "instead. Forty. Forty-one. His jaw had locked shut from the shivering and his "
            "breath came out in short, shallow pulls that never quite reached the bottom of "
            "his chest. Two headlights swung around the bend and he stepped down into the ditch "
            "and waited there, knee-deep, until they passed."
        ),
    },
    {
        "id": "novel_farewell",
        "title": "Platform goodbye",
        "note": "written for this run; warmth and grief in the same breath",
        "text": (
            "She held on longer than either of them expected, and he felt the whole front of "
            "his coat go warm where she pressed against it, the good heavy warmth of someone "
            "who has been standing in a heated waiting room. Her scarf smelled of the kitchen "
            "at home. He kept one hand flat between her shoulder blades and did not move it. "
            "The announcement came twice. When she finally stepped back her eyes were wet and "
            "she laughed at herself for it, and he laughed too, and something in his throat "
            "closed and stayed closed. She got on. The window fogged where she leaned against "
            "it. He stood on the platform with his palms still holding her warmth for another "
            "half minute, until the wind took it, and then there was only the cold rail under "
            "his hand and the long walk back to the car."
        ),
    },
    {
        "id": "novel_waiting_room",
        "title": "Waiting room, 2 a.m.",
        "note": "written for this run; pain foregrounded, fear and a flicker of warmth under it",
        "text": (
            "The wrist had swollen over the strap of the watch and every small movement of the "
            "forearm sent a bright line up to the elbow, so he learned to hold it against his "
            "stomach and breathe around it. The plastic chair pressed a ridge into the back of "
            "his thighs. He read the fire-exit sign eleven times. Each time the door opened he "
            "looked up and each time it was not for him, and the not-being-for-him settled "
            "heavier than the waiting itself. A nurse came by with a blanket from the warmer "
            "and put it over his knees without saying anything, and for a moment the heat "
            "soaked down through the denim and he wanted, absurdly, to cry about it. Then she "
            "was gone and the throb came back up through the wrist, steady as a clock."
        ),
    },
    {
        "id": "novel_neutral_ctrl",
        "title": "Expository control",
        "note": "written for this run; flat procedural prose, the all-pale prediction",
        "text": (
            "A single-stream recycling facility separates mixed material in stages. The intake "
            "conveyor first passes under a rotating drum that pulls off anything larger than "
            "the aperture, which removes most cardboard. A series of inclined disc screens then "
            "sorts by shape: flat items ride over the top of the discs while containers tumble "
            "back and fall through. An eddy current unit induces a field in non-ferrous metal "
            "and flings aluminium off the end of the belt, while an overhead magnet lifts steel "
            "cans earlier in the line. What remains is graded optically, with near-infrared "
            "sensors identifying polymer type and timed air jets diverting each resin into its "
            "own bunker. Manual quality control stations sit at the end of most lines. Throughput "
            "for a mid-sized plant is typically twenty to thirty tonnes per hour."
        ),
    },
]


def word_count(s: str) -> int:
    return len(s.split())


def pick_anchor(group: str, acts_path: str, groups: list[str], lo: int, hi: int, rank: int) -> dict:
    """Return the `rank`-th held-out story of `group` whose length is in [lo, hi]."""
    z = np.load(acts_path, allow_pickle=True)
    labels, ids = z["labels"], [str(x) for x in z["ids"]]
    stored = [str(x) for x in z["groups"]]
    if stored != groups:
        raise SystemExit(f"{acts_path} stores {stored}, expected {groups}")
    _, test = split_indices(labels, 8, 7, groups)
    held = {ids[i] for i in test if labels[i] == groups.index(group)}

    rows = []
    with open(os.path.join(DATA, f"stories_{group}.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in held and lo <= word_count(r["text"]) <= hi:
                rows.append(r)
    if not rows:
        raise SystemExit(f"no held-out {group} story in [{lo},{hi}] words")
    rows.sort(key=lambda r: r["id"])
    r = rows[rank % len(rows)]
    return {
        "id": f"anchor_{group}",
        "family": "anchor",
        "title": f"{group} anchor ({r['id']})",
        "note": f"held-out anchor story, topic: {r['topic']}; {len(rows)} candidates in range",
        "expect": group,
        "text": r["text"],
    }


def lift_steering(path: str, label: str, coeff: float, prompt: int) -> str:
    """Pull one `### <label>` / `**coeff +c x norm | prompt n**` blockquote."""
    want_head = f"### {label}"
    want_cond = f"**coeff {coeff:+.1f} x norm | prompt {prompt}**"
    in_section = False
    buf: list[str] = []
    grabbing = False
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith("### "):
                in_section = line.strip() == want_head
                continue
            if not in_section:
                continue
            if line.startswith("**coeff "):
                if grabbing:
                    break
                grabbing = line.startswith(want_cond)
                continue
            if grabbing and line.startswith("> "):
                buf.append(line[2:])
            elif grabbing and line.strip() == "" and buf:
                buf.append("")
    if not buf:
        raise SystemExit(f"could not find {want_head} / {want_cond} in {path}")
    txt = "\n".join(buf).strip()
    # The generator was cut off at max_new_tokens, so the tail is a half sentence.
    # Left as-is: truncating it would change the token sequence the model saw.
    return re.sub(r"\n{3,}", "\n\n", txt)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=int, default=60)
    ap.add_argument("--hi", type=int, default=150)
    ap.add_argument("--out", default=os.path.join(DATA, "heatmap_texts.json"))
    args = ap.parse_args()

    passages: list[dict] = []

    for g in ["happy", "sad", "angry", "fearful"]:
        passages.append(pick_anchor(g, os.path.join(DATA, "acts.npz"), EMO_GROUPS, args.lo, args.hi, 0))
    for g in ["warm", "cold", "pain"]:
        passages.append(pick_anchor(g, os.path.join(DATA, "acts_sens.npz"), SENS_GROUPS, args.lo, args.hi, 0))
    n = pick_anchor("neutral", os.path.join(DATA, "acts.npz"), EMO_GROUPS, args.lo, args.hi, 0)
    n["expect"] = "none"
    passages.append(n)

    src = os.path.join(RESULTS, "steering_samples_sensation_qwen.md")
    for label, coeff, prompt, pid, caption in STEER_PICKS:
        passages.append(
            {
                "id": pid,
                "family": "steer",
                "title": caption,
                "note": f"lifted verbatim from {os.path.basename(src)} (hs17, dirs_raw, seed 1234)",
                "expect": label,
                "text": lift_steering(src, label, coeff, prompt),
            }
        )

    for row in NOVEL:
        passages.append(
            {
                "id": row["id"],
                "family": "novel",
                "title": row["title"],
                "note": row["note"],
                "expect": "mixed" if "neutral" not in row["id"] else "none",
                "text": " ".join(row["text"].split()),
            }
        )

    for p in passages:
        p.setdefault("family", "anchor")
        p["words"] = word_count(p["text"])

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"passages": passages}, f, indent=2, ensure_ascii=False)

    print(f"-> {args.out}  ({len(passages)} passages)")
    for p in passages:
        print(f"  {p['family']:7s} {p['id']:26s} {p['words']:4d}w  expect={p['expect']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
