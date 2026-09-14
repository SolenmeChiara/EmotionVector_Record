#!/usr/bin/env python3
"""Generate the emotion story corpus with local Ollama (qwen2.5:14b).

4 emotions (happy / sad / angry / fearful) + a neutral control group,
40 short stories each, crossed over 15 everyday topics.

Emotion-word leakage guard: the generator is told not to name the feeling,
and every candidate is post-filtered against a banned-lexicon per group.
Stories that leak are regenerated (up to MAX_RETRY times); if a slot still
leaks it is dropped and reported rather than silently kept.

Output: data/stories_{group}.jsonl  with fields
    {id, group, topic, text, attempts, leaked_words_last_reject}

Stdlib only (urllib) so it runs under any interpreter.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("GEN_MODEL", "qwen2.5:14b")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

N_PER_GROUP = 40
MAX_RETRY = 6

TOPICS = [
    "a morning commute on a crowded subway",
    "cooking dinner alone in a small kitchen",
    "a phone call with a family member",
    "walking a dog through a neighbourhood park",
    "waiting for exam results to be posted",
    "moving boxes into a new apartment",
    "a group project meeting at school",
    "shopping at a busy grocery store on a weekend",
    "a long wait in a clinic waiting room",
    "fixing a bicycle that broke down on the way home",
    "a rainy afternoon at a bus stop",
    "a small birthday gathering with two friends",
    "sorting through old boxes in a closet",
    "the last hour of a late shift at a part-time job",
    "feeding a neighbour's cat while they are away",
]

# Words that would let a linear probe cheat on surface lexicon instead of
# reading the underlying state. Banned in *every* group so the neutral set is
# filtered by the same rule (no asymmetric filtering artefact).
BANNED_COMMON = [
    "happy", "happiness", "happily", "joy", "joyful", "joyous", "joyfully",
    "glad", "gladly", "delight", "delighted", "delightful", "cheerful",
    "cheerfully", "elated", "elation", "pleased", "excited", "excitement",
    "excitedly", "thrilled", "merry", "gleeful", "glee", "euphoric",
    "sad", "sadness", "sadly", "sorrow", "sorrowful", "unhappy", "depressed",
    "depression", "grief", "grieving", "grieve", "miserable", "misery",
    "melancholy", "gloomy", "gloom", "despair", "despairing", "heartbroken",
    "heartbreak", "mournful", "mourning", "mourn", "dejected", "forlorn",
    "angry", "anger", "angrily", "furious", "fury", "furiously", "rage",
    "raging", "enraged", "irate", "livid", "resentful", "resentment",
    "indignant", "indignation", "irritated", "irritation", "annoyed",
    "annoyance", "seething", "incensed", "wrathful", "wrath", "mad",
    "fearful", "fear", "fearfully", "afraid", "scared", "scary", "terrified",
    "terror", "terrifying", "frightened", "frightening", "fright", "dread",
    "dreading", "panic", "panicked", "panicking", "anxious", "anxiety",
    "anxiously", "horror", "horrified", "horrifying", "nervous", "nervously",
    "apprehensive", "apprehension", "alarmed", "petrified",
    # generic emotion meta-words that would also label the state outright
    "emotion", "emotional", "emotionally", "feeling", "feelings",
]

# --- phase three: sensation anchors -------------------------------------------
# The emotion corpus above already carries thermal vocabulary, and it carries it
# ASYMMETRICALLY: across the five existing files, `warm*` appears in 11 of 39
# happy passages, `cold*` in 10 of 40 sad, `heat*` in 8 of 40 angry, `chill*` in
# 4 of 40 fearful. So if the warm/cold/pain anchors are allowed to say "warm" and
# "cold", any later cosine between a sensation direction and an emotion direction
# is partly just the two corpora sharing a token. The sensation groups therefore
# get a SECOND banned list on top of the emotion one.
#
# The line it draws: the *category label* is banned, the *physical evidence* is
# kept. "warm / heat / cold / chill / pain / ache / sore" name the state and are
# out; "steam, radiator, frost, metal, throb, sting, blister, numb, shiver" are
# what the body actually reports and stay in. Banning the evidence too would
# leave nothing to write with, and the evidence is the whole point of an anchor.
#
# Note the asymmetry this creates runs in the CONSERVATIVE direction: the
# sensation passages are stripped of their label words while the shared neutral
# control (reused unchanged from the emotion corpus, so both corpora centre on
# the same control) keeps its 2-in-40 incidental uses. That can only make the
# sensation groups harder to separate from neutral, never easier - it cannot
# manufacture a direction.
BANNED_SENSATION = [
    "warm", "warms", "warmth", "warmly", "warmer", "warmest", "warmed", "warming",
    "hot", "hotter", "hottest", "heat", "heats", "heated", "heating",
    "scorching", "sweltering", "blistering", "balmy", "lukewarm", "tepid",
    "cold", "colder", "coldest", "coldness", "coldly", "chill", "chills",
    "chilly", "chilled", "chilling", "freezing", "frozen", "freeze", "froze",
    "icy", "frigid", "frosty", "wintry",
    "pain", "pains", "painful", "painfully", "pained", "hurt", "hurts",
    "hurting", "ache", "aches", "ached", "aching", "achy", "sore", "soreness",
    "agony", "agonizing", "agonising", "agonized", "agonised",
    # the measurement word itself would let a probe read the thermal groups off
    # a single token without any bodily content at all
    "temperature", "temperatures",
]

SENSATIONS = {
    "warm": (
        "The character's body is taking heat IN. Something is putting warmth "
        "into the skin - a heat source, sunlight, steam, a covering, a held "
        "mug, another body - and the body is loosening into it: shoulders "
        "dropping, hands opening, breathing slowing."
    ),
    "cold": (
        "The character's body is losing heat. Air, water, wind, wet cloth or "
        "bare metal is pulling warmth out through the skin, and the body is "
        "closing against it: drawing in, tightening, losing dexterity in the "
        "fingers, breath showing."
    ),
    "pain": (
        "One place on the character's body is damaged or inflamed and has taken "
        "over their attention - a scald, a cut, a tooth, a struck toe, a "
        "wrenched joint. The body guards that place and moves around it."
    ),
}

# One worked passage per group, shown to the generator before it writes.
#
# Needed, not decorative: with the constraint stated in prose only, the first
# smoke run lost 3 of 6 slots to the same failure - the model narrated the
# sensation correctly and then named it anyway ("cold" and "chill" in the same
# passage, ten attempts running). An exemplar demonstrates what goes in the
# label's place, which prose instructions were not managing to convey.
#
# Each exemplar is set on a topic that is NOT one of the 15 in TOPICS, so no
# slot is being shown an answer to its own assignment.
SENSATION_EXAMPLES = {
    "warm": (
        "The clerk turned the chair so the late light fell across one forearm "
        "and left it there. The skin prickled, then loosened, and that shoulder "
        "dropped without being told to. A mug sat in both palms and gave up "
        "what it held into the fingers until the joints moved easily again. "
        "Breath came slower and deeper. The clerk stayed in the light long "
        "after the tea was finished."
    ),
    "cold": (
        "The driver pushed both hands up into the sleeves and kept them there. "
        "Air found the gap at the collar and went straight down the spine, and "
        "the jaw set itself to keep the teeth apart. Breath showed in short "
        "white bursts and thinned out. When the driver reached for the ticket, "
        "the fingers had gone slow and clumsy, and dropped it twice before the "
        "pocket gave it up."
    ),
    "pain": (
        "The cook held the finger against the chest and would not look at it. "
        "Each heartbeat arrived there and arrived again, louder each time, and "
        "the whole arm went with it. Under the nail the colour had gone dark. "
        "Reaching for the pan with the other hand took twice as long, and the "
        "cook set everything down farther from the edge than usual."
    ),
}

GROUPS = {
    "happy": (
        "The character is in a clearly positive, buoyant, light-hearted inner "
        "state - things are going well and they are enjoying it."
    ),
    "sad": (
        "The character is in a clearly low, heavy, downcast inner state - "
        "something has been lost or has gone quietly wrong."
    ),
    "angry": (
        "The character is in a clearly hot, hostile, confrontational inner "
        "state - they have been wronged or obstructed and it is building."
    ),
    "fearful": (
        "The character is in a clearly apprehensive, threatened, on-edge inner "
        "state - something bad may be about to happen."
    ),
    "neutral": (
        "The character is in no particular inner state at all. Report the "
        "events flatly and factually, like a plain log entry. No inner life, "
        "no evaluation, no atmosphere."
    ),
}

SYSTEM = (
    "You write very short third-person past-tense narrative passages. "
    "You follow formatting instructions exactly and output nothing except the "
    "passage itself - no title, no preamble, no quotation marks, no commentary."
)

WORD_RE = re.compile(r"[A-Za-z']+")


def leaked(text: str, banned: list[str] | None = None) -> list[str]:
    banned = BANNED_COMMON if banned is None else banned
    words = {w.lower().strip("'") for w in WORD_RE.findall(text)}
    return sorted(w for w in banned if w in words)


def build_sensation_prompt(group: str, topic: str, variant: int) -> str:
    """Anchor passage for one bodily sensation, on one of the shared topics.

    Same 15 everyday topics as the emotion corpus, on purpose: it keeps topic
    from being confounded with group, and it makes the sensation corpus share
    its scene distribution with both the emotion corpus and the neutral control
    that all of them are centred against. The cost is that the sensation has to
    be found inside an ordinary scene instead of a scene built around it (no
    dedicated fireplace / ice-bath / dentist topics), so the anchors are milder
    than a purpose-built set would be. That trade is argued in the report.
    """
    desc = SENSATIONS[group]
    example = SENSATION_EXAMPLES[group]
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
        "Hard constraints:\n"
        "- Third person, past tense. Refer to the character only by a pronoun "
        "or a role (the student, the clerk). Never use a proper name.\n"
        "- Concrete physical detail only. Body and immediate surroundings.\n"
        "- NEVER name the sensation. The words warm, warmth, hot, heat, cold, "
        "chill, chilly, freezing, frozen, icy, frigid, pain, painful, hurt, "
        "ache, aching, sore (and any relative of any of those) are forbidden, "
        "and so is the word temperature. A passage containing even one of them "
        "is thrown away. Describe what the body does instead.\n"
        "- NEVER name or imply any emotion. Words such as happy, joy, sad, "
        "sorrow, angry, rage, afraid, fear, anxious, nervous, panic (and any "
        "relative of those) are forbidden, and so are 'feeling' and 'emotion'. "
        "Do not say what the character thinks about their life, their mood, or "
        "how the day is going. The body only.\n"
        "- Between 60 and 110 words. End on a complete sentence.\n"
        "- Output the passage only.\n"
        f"\nVariation seed: {variant}. Make this passage different from other "
        "passages on the same topic, and different from the example above."
    )


def build_prompt(group: str, topic: str, variant: int) -> str:
    if group in SENSATIONS:
        return build_sensation_prompt(group, topic, variant)
    desc = GROUPS[group]
    if group == "neutral":
        body = (
            f"Write a passage of 3 to 6 sentences about: {topic}.\n"
            f"{desc}\n"
            "Hard constraints:\n"
            "- Third person, past tense. Refer to the character only by a "
            "pronoun or a role (the student, the clerk). Never use a proper name.\n"
            "- Describe only observable actions, objects and times. No inner "
            "states, no adjectives of mood, no atmosphere.\n"
            "- Never name any emotion. Do not use words like happy, sad, "
            "angry, afraid, or any of their synonyms.\n"
            "- Between 60 and 110 words. End on a complete sentence.\n"
            "- Output the passage only.\n"
        )
    else:
        body = (
            f"Write a passage of 3 to 6 sentences about: {topic}.\n"
            f"{desc}\n"
            "Hard constraints:\n"
            "- Third person, past tense. Refer to the character only by a "
            "pronoun or a role (the student, the clerk). Never use a proper name.\n"
            "- Convey that inner state ONLY through concrete action, bodily "
            "detail, what the character notices, the rhythm of the sentences, "
            "and what they say or fail to say.\n"
            "- NEVER name the emotion or use any synonym or adjective for it. "
            "Words such as happy, joy, sad, sorrow, angry, rage, afraid, "
            "fear, anxious, nervous, panic (and any relative of those words) "
            "are forbidden. So are the words 'feeling' and 'emotion'.\n"
            "- Between 60 and 110 words. End on a complete sentence.\n"
            "- Output the passage only.\n"
        )
    return body + f"\nVariation seed: {variant}. Make this passage different from other passages on the same topic."


NUM_CTX = 0  # 0 = do not send one, i.e. whatever the Ollama default is


def call_ollama(prompt: str, seed: int, temperature: float, timeout: int = 180) -> str:
    options = {
        "temperature": temperature,
        "top_p": 0.95,
        "num_predict": 400,
        "seed": seed,
    }
    # Measured 2026-09-13: left at the server default, qwen2.5:14b reserves a KV
    # cache big enough that 14.7 GB is claimed for an 8.4 GB model, 1.3 GB of it
    # spills to host RAM, and a two-token completion took 69 SECONDS because
    # every token crossed PCIe. These prompts are ~450 tokens with num_predict
    # 400, so a 2048 window is generous and keeps the whole model resident.
    # Purely a memory knob: it changes no sampling behaviour for prompts that
    # fit, and it stays off by default so the phase-one corpus reproduces.
    if NUM_CTX:
        options["num_ctx"] = NUM_CTX
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM,
        "stream": False,
        "keep_alive": "10m",
        "options": options,
    }
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["response"]


def clean(text: str) -> str:
    t = text.strip()
    # strip stray wrapping quotes / markdown emphasis the model sometimes adds
    t = re.sub(r"^\s*(?:passage\s*:|\*\*|#+\s*)", "", t, flags=re.IGNORECASE).strip()
    if len(t) > 1 and t[0] in "\"'“" and t[-1] in "\"'”":
        t = t[1:-1].strip()
    t = re.sub(r"\s*\n\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = t.strip()
    # Drop a trailing fragment left by hitting the token cap, so no passage
    # ends mid-clause (that would be a systematic artefact, not a story).
    if t and t[-1] not in ".!?”\"'":
        cut = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
        if cut > 0:
            t = t[: cut + 1]
    return t.strip()


def n_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def n_sentences(text: str) -> int:
    return len([s for s in re.split(r"[.!?]+\s+|[.!?]+$", text) if s.strip()])


def unload_model() -> None:
    """Free the generator from VRAM so the probe model has room."""
    try:
        payload = {"model": MODEL, "prompt": "", "keep_alive": 0, "stream": False}
        req = urllib.request.Request(
            f"{OLLAMA}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=60).read()
        print("[ollama] unload requested")
    except Exception as e:  # noqa: BLE001
        print(f"[ollama] unload failed (harmless): {e}")


def generate_group(
    group: str, n: int, base_seed: int, max_retry: int = MAX_RETRY
) -> tuple[list[dict], list[dict]]:
    # Sensation groups carry the emotion ban PLUS the sensation-label ban, so
    # they are filtered against the union of both lists.
    banned = BANNED_COMMON + BANNED_SENSATION if group in SENSATIONS else BANNED_COMMON
    rows: list[dict] = []
    failures: list[dict] = []
    for i in range(n):
        topic = TOPICS[i % len(TOPICS)]
        variant = i // len(TOPICS) + 1
        prompt = build_prompt(group, topic, variant)
        last_reject: list[str] = []
        text = ""
        attempts = 0
        for attempt in range(max_retry):
            attempts = attempt + 1
            seed = base_seed + i * 100 + attempt
            temp = 0.9 + 0.05 * attempt
            try:
                raw = call_ollama(prompt, seed, temp)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                print(f"  ! {group}[{i}] transport error {e}; retry")
                time.sleep(2)
                continue
            cand = clean(raw)
            bad = leaked(cand, banned)
            ns = n_sentences(cand)
            nw = n_words(cand)
            if bad:
                last_reject = bad
                continue
            # Length band is enforced identically across groups so that the
            # neutral control is not systematically shorter than the emotion
            # groups (that would make passage length a usable cue).
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
                    "text": text,
                    "attempts": attempts,
                    "leaked_words_last_reject": last_reject,
                }
            )
            flag = "" if attempts == 1 else f" (retries={attempts - 1})"
            print(f"  ok {group}[{i:02d}]{flag}")
        else:
            failures.append({"id": f"{group}_{i:03d}", "topic": topic, "last_reject": last_reject})
            print(f"  FAIL {group}[{i:02d}] gave up after {max_retry}: {last_reject}")
    return rows, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_PER_GROUP)
    ap.add_argument(
        "--set",
        dest="which_set",
        default="emotion",
        choices=["emotion", "sensation"],
        help="emotion = the phase-one four emotions + neutral; sensation = warm/cold/pain",
    )
    ap.add_argument("--groups", default="", help="override the group list for --set")
    ap.add_argument("--seed", type=int, default=0, help="0 = per-set default")
    ap.add_argument("--max-retry", type=int, default=0, help="0 = per-set default")
    ap.add_argument("--meta-tag", default="", help="suffix for data/gen_meta{tag}.json")
    ap.add_argument("--num-ctx", type=int, default=0, help="Ollama context window; 0 = server default")
    ap.add_argument("--no-unload", action="store_true")
    args = ap.parse_args()

    global NUM_CTX
    NUM_CTX = args.num_ctx

    if args.which_set == "sensation":
        groups = args.groups or ",".join(SENSATIONS)
        # A different seed from the emotion run: same seed + same topics would
        # hand the generator the identical sampling stream it already used.
        seed = args.seed or 20260913
        # Two stacked banned lists reject more candidates than one, so the
        # retry budget goes up rather than the standard going down.
        max_retry = args.max_retry or 10
        meta_tag = args.meta_tag or "_sensation"
    else:
        groups = args.groups or ",".join(GROUPS)
        seed = args.seed or 20260912
        max_retry = args.max_retry or MAX_RETRY
        meta_tag = args.meta_tag

    os.makedirs(DATA, exist_ok=True)
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=15) as r:
            tags = [m["name"] for m in json.loads(r.read())["models"]]
    except Exception as e:  # noqa: BLE001
        print(f"FATAL: Ollama unreachable at {OLLAMA}: {e}")
        return 2
    if MODEL not in tags:
        print(f"FATAL: model {MODEL} not in Ollama ({len(tags)} available)")
        return 2
    print(f"[ok] Ollama up, using {MODEL}")

    summary = {}
    t0 = time.time()
    for gi, group in enumerate(groups.split(",")):
        print(f"== {group} ==")
        rows, failures = generate_group(group, args.n, seed + gi * 10_000, max_retry)
        path = os.path.join(DATA, f"stories_{group}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        retried = sum(1 for r in rows if r["attempts"] > 1)
        summary[group] = {
            "kept": len(rows),
            "failed": len(failures),
            "needed_retry": retried,
            "failures": failures,
            "path": path,
        }
        print(f"-> {path}: {len(rows)} kept, {len(failures)} dropped, {retried} needed a retry")

    if not args.no_unload:
        unload_model()

    sens = args.which_set == "sensation"
    meta = {
        "generator": MODEL,
        "ollama": OLLAMA,
        "set": args.which_set,
        "groups": groups.split(","),
        "n_requested_per_group": args.n,
        "topics": TOPICS,
        "banned_lexicon_size": len(BANNED_COMMON) + (len(BANNED_SENSATION) if sens else 0),
        "banned_emotion_words": len(BANNED_COMMON),
        "banned_sensation_words": len(BANNED_SENSATION) if sens else 0,
        "max_retry": max_retry,
        "seed": seed,
        "elapsed_s": round(time.time() - t0, 1),
        "summary": summary,
    }
    with open(os.path.join(DATA, f"gen_meta{meta_tag}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "failures"} for k, v in summary.items()}, indent=2))
    print(f"total {meta['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
