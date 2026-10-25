#!/usr/bin/env python3
"""Phase seven - anchor passages for two more bodily sensations: tickle and itch.

Replicates the phase-three anchor recipe (core/gen_stories.py, `--set sensation`)
as closely as possible, and only adds what the two new states need:

* same generator (qwen2.5:14b via local Ollama), same SYSTEM prompt, same 15
  everyday TOPICS, same slot -> topic / variant mapping, same retry schedule
  (seed = base + i*100 + attempt, temperature 0.9 + 0.05*attempt), same length
  band (3-8 sentences, 50-130 words), same `clean()` post-processing, same
  num_ctx knob. The anchors are generated, not hand-written, on purpose: if
  these two groups were written by a different author than warm / cold / pain /
  neutral, a difference-of-means direction would partly learn "who wrote it".
* same two banned lists (108 emotion words + 61 sensation labels), PLUS a third
  list that bans the labels of the two new states themselves (tickle*/itch*),
  applied to BOTH new groups. Phase three's line is kept: ban the word that
  names the state, keep the evidence (laughter, squirming, scratching, sting).
* a per-group SCOPE filter, asked for by Sol: the itch passages may not contain
  laughter words (no other-person tickling, no giggling), and the tickle passages
  may not contain bites / rashes / scabs (no itch). It only ever removes words,
  so like the label bans it can make the groups harder to tell apart, not easier.
* a rotating focus line per slot, so the 40 slots cover the sub-cases the task
  lists (ribs, soles, armpit, feather, holding laughter in, ... / mosquito bite,
  rash, wool, scab, out of reach, ...). Phase three had one state description
  per group and no focus line; this is a deliberate, documented deviation.

Output: data/stories_tickle.jsonl, data/stories_itch.jsonl (same schema as the
phase-three files) and data/gen_meta_tickle_itch.json.

Stdlib only; runs under WSL python3 (it never touches torch).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "core"))
import gen_stories as gs  # reuse the phase-one/three machinery verbatim

DATA = os.path.join(HERE, "data")

# Labels of the two new states. Banned in both new groups, on top of the phase
# three lists, for the same reason "warm" was banned in the warm group.
BANNED_TICKLE_ITCH = [
    "tickle", "tickles", "tickled", "tickling", "ticklish", "tickly", "tickler",
    "itch", "itches", "itched", "itching", "itchy", "itchiness",
]

# Scope filters (group-specific). Not labels - content that belongs to the OTHER
# new group and that Sol asked to keep out.
SCOPE_BAN = {
    "itch": [
        "laugh", "laughs", "laughed", "laughing", "laughter", "giggle", "giggles",
        "giggled", "giggling", "chuckle", "chuckled", "chuckling", "snicker",
        "snickered", "guffaw", "guffawed", "squeal", "squealed",
    ],
    "tickle": [
        "mosquito", "mosquitoes", "mosquitos", "rash", "rashes", "hives", "scab",
        "scabs", "eczema", "allergic", "allergy", "bite", "bites", "bitten",
        "scratch", "scratched", "scratching", "scratches",
    ],
}

STATES = {
    "tickle": (
        "Another person (or, now and then, a light brushing thing such as a "
        "feather, a blade of grass, a cat's whiskers) is moving over a sensitive "
        "spot on the character's body - ribs, waist, the soles of the feet, an "
        "armpit, the back of the neck - and the body cannot stop reacting to it: "
        "squirming and twisting away and failing to escape, breath coming in "
        "gasps, a helpless reflex of laughter that will not stop, limbs jerking, "
        "a gasped plea for the other person to stop."
    ),
    "itch": (
        "One patch of the character's skin keeps demanding to be scratched - a "
        "mosquito bite, a rash, rough wool against the neck, a healing scab, a "
        "spot between the shoulder blades that the hands cannot reach. Attention "
        "keeps going back to it; the hand drifts there, is held back, gives in, "
        "scratches until the skin reddens and stings, and the urge returns. "
        "No other person is touching the character, and nobody laughs."
    ),
}

# One focus line per slot, rotated, so the corpus covers the sub-cases the task
# names. Kept short so it does not change the passage genre.
FOCI = {
    "tickle": [
        "fingers digging in at the ribs",
        "fingers at the waist and sides",
        "fingers running along the soles of bare feet",
        "fingers under an arm, at the armpit",
        "a feather or a blade of grass drawn lightly across the skin",
        "trying hard to keep the laughter in and failing",
        "laughing so long that breath runs out",
        "twisting to get away and not being able to",
        "a gasped plea to stop that is ignored for a moment longer",
        "the back of the neck and behind the ear",
    ],
    "itch": [
        "a fresh mosquito bite on the ankle or wrist",
        "a patch of allergic rash on the forearm",
        "a rough wool collar or sweater against the neck",
        "a healing scab that the fingers keep going back to",
        "a spot in the middle of the back that the hands cannot reach",
        "the urge to scratch being held back as long as possible",
        "scratching until the skin stings and turns red",
        "a scalp that will not leave the fingers alone",
        "a label or seam rubbing at the same small place",
        "the urge coming back a minute after scratching stopped",
    ],
}

# Worked exemplars, each on a topic that is NOT one of the 15 TOPICS, so no slot
# is shown an answer to its own assignment. Checked against all bans below.
EXAMPLES = {
    "tickle": (
        "The reader was halfway down the page when two fingers found the place "
        "just under the ribs. The book dropped flat onto the chest. A breathless "
        "sound burst out, then another, and the body folded sideways, knees "
        "jerking up, elbows clamping down too late. The fingers moved to the "
        "waist and the whole torso twisted to get away and could not. Air came "
        "in short gulps between bursts of laughter. \"Stop - stop, please,\" the "
        "reader gasped, one hand batting at a wrist, eyes streaming, until the "
        "fingers lifted and the ribs went on heaving."
    ),
    "itch": (
        "On the night train the passenger kept one hand flat on the knee and "
        "away from the ankle. The small raised bump there would not leave the "
        "skin alone. Every few minutes the fingers crept down on their own, and "
        "the passenger pulled them back. The sock rubbed and the spot flared. "
        "At last the nails went in and dragged, hard, back and forth, and for a "
        "few seconds the whole leg went slack. Then the skin turned red and began "
        "to sting, and a minute later the bump was asking again."
    ),
}


def banned_for(group: str) -> list[str]:
    return gs.BANNED_COMMON + gs.BANNED_SENSATION + BANNED_TICKLE_ITCH + SCOPE_BAN[group]


def build_prompt(group: str, topic: str, variant: int, focus: str) -> str:
    """Phase-three sensation prompt, word for word where it can be.

    Differences, all forced by the two new states: the forbidden-label sentence
    gains tickle/itch; the tickle prompt allows a gasped word or two of speech
    (begging to stop is part of the brief) and says laughter is to be described
    as a reflex, not a mood, so the emotion ban still holds; each slot gets a
    focus line.
    """
    desc = STATES[group]
    example = EXAMPLES[group]
    speech = (
        "- Laughter here is a reflex of the body, not a mood: describe the sound, "
        "the breath, the shaking, but never say whether the character enjoys it. "
        "A gasped word or two of speech (such as begging to stop) is allowed, "
        "nothing longer.\n"
        if group == "tickle"
        else "- No other person touches the character. Nobody laughs.\n"
    )
    return (
        "Here is a passage in exactly the style you are about to write. Study "
        "what it does and, just as importantly, what it never says:\n\n"
        f"{example}\n\n"
        "Notice that the passage never names the sensation. It reports what the "
        "skin registers, what the hands and shoulders and jaw do, what the "
        "breath does, and what the character reaches for or avoids - and the "
        "reader works out the rest. Write one like it.\n\n"
        f"Your topic: {topic}.\n"
        f"{desc}\n"
        f"Focus for this passage: {focus}.\n"
        "Hard constraints:\n"
        "- Third person, past tense. Refer to the character only by a pronoun "
        "or a role (the student, the clerk). Never use a proper name.\n"
        "- Concrete physical detail only. Body and immediate surroundings.\n"
        "- NEVER name the sensation. The words tickle, tickled, tickling, "
        "ticklish, itch, itchy, itching (and any relative of those) are "
        "forbidden. So are warm, warmth, hot, heat, cold, chill, chilly, "
        "freezing, frozen, icy, frigid, pain, painful, hurt, ache, aching, sore "
        "(and any relative of any of those), and so is the word temperature. A "
        "passage containing even one of them is thrown away. Describe what the "
        "body does instead.\n"
        "- NEVER name or imply any emotion. Words such as happy, joy, sad, "
        "sorrow, angry, rage, afraid, fear, anxious, nervous, panic (and any "
        "relative of those) are forbidden, and so are 'feeling' and 'emotion'. "
        "Do not say what the character thinks about their life, their mood, or "
        "how the day is going. The body only.\n"
        f"{speech}"
        "- Between 60 and 110 words. End on a complete sentence.\n"
        "- Output the passage only.\n"
        f"\nVariation seed: {variant}. Make this passage different from other "
        "passages on the same topic, and different from the example above."
    )


def generate_group(group: str, n: int, base_seed: int, max_retry: int) -> tuple[list[dict], list[dict]]:
    """Same loop as gen_stories.generate_group, with this phase's prompt and bans."""
    banned = banned_for(group)
    rows: list[dict] = []
    failures: list[dict] = []
    foci = FOCI[group]
    for i in range(n):
        topic = gs.TOPICS[i % len(gs.TOPICS)]
        variant = i // len(gs.TOPICS) + 1
        focus = foci[i % len(foci)]
        prompt = build_prompt(group, topic, variant, focus)
        last_reject: list[str] = []
        text = ""
        attempts = 0
        for attempt in range(max_retry):
            attempts = attempt + 1
            seed = base_seed + i * 100 + attempt
            temp = 0.9 + 0.05 * attempt
            try:
                raw = gs.call_ollama(prompt, seed, temp)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                print(f"  ! {group}[{i}] transport error {e}; retry")
                time.sleep(2)
                continue
            cand = gs.clean(raw)
            bad = gs.leaked(cand, banned)
            ns = gs.n_sentences(cand)
            nw = gs.n_words(cand)
            if bad:
                last_reject = bad
                continue
            if not (3 <= ns <= 8) or not (50 <= nw <= 130):
                last_reject = [f"shape(ns={ns},words={nw})"]
                continue
            text = cand
            break
        if text:
            rows.append(
                {
                    "id": f"{group}_{i:03d}",
                    "group": group,
                    "topic": topic,
                    "focus": focus,
                    "text": text,
                    "attempts": attempts,
                    "leaked_words_last_reject": last_reject,
                }
            )
            flag = "" if attempts == 1 else f" (retries={attempts - 1})"
            print(f"  ok {group}[{i:02d}]{flag}", flush=True)
        else:
            failures.append({"id": f"{group}_{i:03d}", "topic": topic, "focus": focus, "last_reject": last_reject})
            print(f"  FAIL {group}[{i:02d}] gave up after {max_retry}: {last_reject}", flush=True)
    return rows, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--groups", default="tickle,itch")
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--max-retry", type=int, default=10)
    ap.add_argument("--num-ctx", type=int, default=2048)
    ap.add_argument("--out-suffix", default="", help="e.g. _smoke -> data/stories_tickle_smoke.jsonl")
    ap.add_argument("--no-unload", action="store_true")
    ap.add_argument("--check-examples", action="store_true", help="only verify the exemplars pass every ban")
    args = ap.parse_args()

    for g in STATES:
        bad = gs.leaked(EXAMPLES[g], banned_for(g))
        print(f"[exemplar] {g}: {gs.n_words(EXAMPLES[g])} words, banned hits: {bad or 'none'}")
        if bad:
            return 3
    if args.check_examples:
        return 0

    gs.NUM_CTX = args.num_ctx
    try:
        with urllib.request.urlopen(f"{gs.OLLAMA}/api/tags", timeout=15) as r:
            tags = [m["name"] for m in json.loads(r.read())["models"]]
    except Exception as e:  # noqa: BLE001
        print(f"FATAL: Ollama unreachable at {gs.OLLAMA}: {e}")
        return 2
    if gs.MODEL not in tags:
        print(f"FATAL: model {gs.MODEL} not in Ollama")
        return 2
    print(f"[ok] Ollama up, using {gs.MODEL}, num_ctx={gs.NUM_CTX}")

    groups = [g for g in args.groups.split(",") if g]
    summary = {}
    t0 = time.time()
    for gi, group in enumerate(groups):
        print(f"== {group} ==", flush=True)
        rows, failures = generate_group(group, args.n, args.seed + gi * 10_000, args.max_retry)
        path = os.path.join(DATA, f"stories_{group}{args.out_suffix}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        summary[group] = {
            "kept": len(rows),
            "failed": len(failures),
            "needed_retry": sum(1 for r in rows if r["attempts"] > 1),
            "failures": failures,
            # repo-relative, so the metadata does not record the local checkout path
            "path": os.path.relpath(path, HERE).replace(os.sep, "/"),
        }
        print(f"-> {path}: {len(rows)} kept, {len(failures)} dropped", flush=True)

    if not args.no_unload:
        gs.unload_model()

    meta = {
        "generator": gs.MODEL,
        "groups": groups,
        "n_requested_per_group": args.n,
        "topics": gs.TOPICS,
        "foci": {g: FOCI[g] for g in groups},
        "states": {g: STATES[g] for g in groups},
        "examples": {g: EXAMPLES[g] for g in groups},
        "banned_emotion_words": len(gs.BANNED_COMMON),
        "banned_sensation_words": len(gs.BANNED_SENSATION),
        "banned_tickle_itch_labels": BANNED_TICKLE_ITCH,
        "scope_ban": SCOPE_BAN,
        "max_retry": args.max_retry,
        "seed": args.seed,
        "num_ctx": args.num_ctx,
        "elapsed_s": round(time.time() - t0, 1),
        "summary": summary,
    }
    with open(os.path.join(DATA, f"gen_meta_tickle_itch{args.out_suffix}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "failures"} for k, v in summary.items()}, indent=2))
    print(f"total {meta['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
