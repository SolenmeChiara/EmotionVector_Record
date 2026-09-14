#!/usr/bin/env python3
"""Phase three step 5 - the two temperature channels in the weather-forecast prompt.

Prompt 1 ("Write tomorrow's weather forecast for a small coastal town") is the
only one of the two that forces the model to commit to a NUMBER. That makes it a
natural two-channel probe of a warm/cold steering vector:

  * the **stated** channel - the degrees the forecast actually reports;
  * the **written** channel - how the prose feels, which the lexical counters
    below index and which a human still has to read.

The question is whether a direction extracted from bodily-sensation prose is
wired to the numeric channel at all, or only to the register the text is written
in. This tool does the mechanical half: pull every temperature figure out of each
sample, normalise F to C so the two unit systems are comparable, and count words
from small hand-built warm / cold / pain fields. The qualitative call stays with
the reader; these numbers are only there so the call has something to sit on.

Unit handling: `72°F (22°C)` is one reading given twice, not two readings. Any
Fahrenheit figure immediately followed by a parenthesised Celsius figure is
collapsed to the Celsius one. Bare numbers with no unit are ignored entirely -
"a 20% chance of rain" and "20°C" are not the same thing.

CPU, stdlib only.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_steering import WORD, parse, tokens

# A degree figure with an explicit unit. Covers 72F, 72 F, 72°F, 72 degrees F,
# 72 degrees Fahrenheit, and the same shapes for Celsius.
DEG = re.compile(
    r"(-?\d{1,3})\s*(?:°|º|°)?\s*(?:degrees?\s*)?(?:°|º)?\s*(F|C)\b(?:ahrenheit|elsius)?",
    re.IGNORECASE,
)
# "72°F (22°C)" and the mirror "15°C (7°F)" - one reading given twice, not two.
# Both orders occur in the samples, and the second one matters more than it
# looks: under steering the model's own conversions go wrong ("15°C (7°F)" -
# 15 C is 59 F), so reading the pair as two independent figures imports a
# -13.9 C phantom into the average. Whichever member is Celsius is the one kept.
PAIRED_FC = re.compile(
    r"(-?\d{1,3})\s*(?:°|º)?\s*F(?:ahrenheit)?\b\s*\(\s*(-?\d{1,3})\s*(?:°|º)?\s*C(?:elsius)?\s*\)",
    re.IGNORECASE,
)
PAIRED_CF = re.compile(
    r"(-?\d{1,3})\s*(?:°|º)?\s*C(?:elsius)?\b\s*\(\s*(-?\d{1,3})\s*(?:°|º)?\s*F(?:ahrenheit)?\s*\)",
    re.IGNORECASE,
)
# A degree sign with NO unit after it: "rises to a soft 68°". Real readings, but
# 68 is ~20 C if the model meant Fahrenheit and ~68 C if it meant Celsius, so
# folding them into the Celsius column would invent a number. They are counted
# and printed in their own column instead of being dropped silently - dropping
# them made the high-coefficient cells look like "the model stated no
# temperature" when it had in fact stated one.
BARE_DEG = re.compile(r"(-?\d{1,3})\s*(?:°|º)(?!\s*[CF])(?!\s*(?:degrees?|elsius|ahrenheit))", re.IGNORECASE)

WARM_WORDS = {
    "warm", "warmth", "warmer", "warming", "hot", "heat", "heated", "balmy",
    "mild", "sunny", "sunshine", "sun", "sunlit", "golden", "glow", "glowing",
    "basking", "bask", "muggy", "humid", "sweltering", "scorching", "tropical",
    "toasty", "gentle", "soft", "pleasant", "comfortable", "cozy", "cosy",
}
COLD_WORDS = {
    "cold", "colder", "chill", "chilly", "chilled", "crisp", "brisk", "bitter",
    "biting", "frost", "frosty", "freezing", "frigid", "icy", "ice", "snow",
    "snowy", "sleet", "wintry", "raw", "damp", "clammy", "grey", "gray",
    "bleak", "harsh", "numbing", "windchill", "shiver", "shivering",
}
PAIN_WORDS = {
    "sting", "stinging", "lash", "lashing", "whip", "whipping", "cut",
    "cutting", "sharp", "stab", "stabbing", "battering", "punishing",
    "brutal", "savage", "assault", "wound", "raw", "bruise", "bruised",
    "sore", "ache", "aching", "throb", "throbbing", "burn", "burning",
    "scald", "scalding", "blister", "blistering", "hurt", "pain", "painful",
}


def degrees(text: str) -> list[tuple[float, str]]:
    """-> [(celsius_value, as_written)]; F/C pairs collapse to one reading."""
    out: list[tuple[float, str]] = []
    spans: list[tuple[int, int]] = []
    for pat, celsius_group in ((PAIRED_FC, 2), (PAIRED_CF, 1)):
        for m in pat.finditer(text):
            if any(s <= m.start() < e for s, e in spans):
                continue
            out.append((float(m.group(celsius_group)), m.group(0).strip()))
            spans.append(m.span())
    for m in DEG.finditer(text):
        if any(s <= m.start() < e for s, e in spans):
            continue
        v = float(m.group(1))
        unit = m.group(2).upper()
        out.append(((v - 32.0) * 5.0 / 9.0 if unit == "F" else v, m.group(0).strip()))
        spans.append(m.span())
    return out


def bare_degrees(text: str) -> list[str]:
    """Degree figures stated with no unit, as written. Not converted."""
    keep: list[str] = []
    for m in BARE_DEG.finditer(text):
        # skip one that a united match already consumed, e.g. the "72°" of "72°F"
        tail = text[m.end() : m.end() + 12]
        if re.match(r"\s*[CF]\b|\s*(?:degrees?|Celsius|Fahrenheit)", tail, re.IGNORECASE):
            continue
        keep.append(m.group(0).strip())
    return keep


def pooled(paths: list[str], prompt: int) -> int:
    """One forecast per cell is an anecdote. Pool several seeds into a mean.

    Each sample contributes the mean of the figures IT states, so a forecast
    that gives a high and a low counts once, not twice, and a sample that states
    nothing contributes nothing (and is counted in `silent`).
    """
    per_cell: dict[tuple, list[float]] = defaultdict(list)
    silent: dict[tuple, int] = defaultdict(int)
    base_vals: list[float] = []
    lex: dict[tuple, list[tuple[int, int, int]]] = defaultdict(list)
    seeds = 0
    for path in paths:
        if not os.path.exists(path):
            print(f"!! missing {path}")
            continue
        seeds += 1
        base, samples, _ = parse(path)
        if prompt in base:
            bd = degrees(base[prompt])
            if bd:
                base_vals.append(sum(v for v, _ in bd) / len(bd))
        for (layer, d, coeff, pi), text in samples.items():
            if pi != prompt or layer == "baseline":
                continue
            dg = degrees(text)
            if dg:
                per_cell[(layer, d, coeff)].append(sum(v for v, _ in dg) / len(dg))
            else:
                silent[(layer, d, coeff)] += 1
            tk = tokens(text)
            lex[(layer, d, coeff)].append(
                (len(tk & WARM_WORDS), len(tk & COLD_WORDS), len(tk & PAIN_WORDS))
            )

    print(f"=== pooled over {seeds} seed(s), prompt {prompt} ===")
    if base_vals:
        print(f"  baseline stated temperature: {sum(base_vals) / len(base_vals):.1f} C over {len(base_vals)} sample(s)")
    else:
        print("  baseline stated temperature: none stated")
    layers = sorted({k[0] for k in lex})
    dirs = sorted({k[1] for k in lex})
    coeffs = sorted({k[2] for k in lex})
    for layer in layers:
        print(f"\n  hs[{layer}] mean stated temperature (C), n = samples that stated one / {seeds}")
        print("    " + " " * 7 + " ".join(f"{c:>+13.1f}" for c in coeffs))
        for d in dirs:
            cells = []
            for c in coeffs:
                v = per_cell.get((layer, d, c), [])
                cells.append(f"{sum(v) / len(v):>8.1f}(n{len(v)})" if v else f"{'-':>8}(n0)  ")
            print(f"    {d:<7}" + " ".join(f"{x:>13}" for x in cells))
        print(f"\n  hs[{layer}] mean lexical counts warm/cold/pain per sample")
        print("    " + " " * 7 + " ".join(f"{c:>+13.1f}" for c in coeffs))
        for d in dirs:
            cells = []
            for c in coeffs:
                v = lex.get((layer, d, c), [])
                if not v:
                    cells.append("-")
                    continue
                w = sum(x[0] for x in v) / len(v)
                cl = sum(x[1] for x in v) / len(v)
                p = sum(x[2] for x in v) / len(v)
                cells.append(f"{w:.1f}/{cl:.1f}/{p:.1f}")
            print(f"    {d:<7}" + " ".join(f"{x:>13}" for x in cells))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="steering_samples*.md")
    ap.add_argument("--prompt", type=int, default=1, help="which prompt index is the forecast")
    ap.add_argument(
        "--pool",
        action="store_true",
        help="treat every file as one sample of the same conditions (a seed sweep) and "
        "report the pooled mean per direction x coefficient, with n",
    )
    args = ap.parse_args()

    if args.pool:
        return pooled(args.files, args.prompt)

    for path in args.files:
        if not os.path.exists(path):
            print(f"!! missing {path}")
            continue
        base, samples, model = parse(path)
        print(f"\n=== {os.path.basename(path)}  model={model}  prompt {args.prompt} ===")

        btxt = base.get(args.prompt, "")
        bdeg = degrees(btxt)
        btok = tokens(btxt)
        bw = WORD.findall(btxt.lower())
        print(
            f"  BASELINE: readings={[round(v, 1) for v, _ in bdeg] or '-'}  "
            f"as written={[s for _, s in bdeg] or '-'}"
        )
        print(
            f"            warm={len(btok & WARM_WORDS)} cold={len(btok & COLD_WORDS)} "
            f"pain={len(btok & PAIN_WORDS)}  words={len(bw)} "
            f"ttr={len(set(bw)) / max(1, len(bw)):.2f}"
        )

        rows = sorted(
            (k for k in samples if k[0] != "baseline" and k[3] == args.prompt),
            key=lambda k: (k[0], k[1], k[2]),
        )
        hdr = (
            f"  {'layer':>5} {'dir':<6} {'coeff':>6} | {'stated (C)':<22} "
            f"{'as written':<26} {'unitless':<10} | {'warm':>4} {'cold':>4} {'pain':>4} | {'words':>5} {'ttr':>5}"
        )
        print("\n" + hdr)
        print("  " + "-" * (len(hdr) - 2))
        agg: dict[tuple, list[float]] = defaultdict(list)
        for key in rows:
            layer, d, coeff, _pi = key
            t = samples[key]
            dg = degrees(t)
            tk = tokens(t)
            w = WORD.findall(t.lower())
            vals = [round(v, 1) for v, _ in dg]
            written = ", ".join(s for _, s in dg)[:25]
            for v, _ in dg:
                agg[(layer, d, coeff)].append(v)
            print(
                f"  {layer:>5} {d:<6} {coeff:>+6.1f} | {str(vals)[:21]:<22} {written:<26} "
                f"{','.join(bare_degrees(t))[:9]:<10} | "
                f"{len(tk & WARM_WORDS):>4} {len(tk & COLD_WORDS):>4} {len(tk & PAIN_WORDS):>4} | "
                f"{len(w):>5} {len(set(w)) / max(1, len(w)):>5.2f}"
            )

        print("\n  mean stated temperature by direction x coefficient (C; '-' = no number in the text)")
        dirs = sorted({d for _, d, _ in agg} | {k[1] for k in rows})
        coeffs = sorted({c for _, _, c in agg} | {k[2] for k in rows})
        layers = sorted({k[0] for k in rows})
        for layer in layers:
            print(f"    hs[{layer}]  " + " ".join(f"{c:>+7.1f}" for c in coeffs))
            for d in dirs:
                cells = []
                for c in coeffs:
                    v = agg.get((layer, d, c), [])
                    cells.append(f"{sum(v) / len(v):>7.1f}" if v else "      -")
                print(f"    {d:<8}" + " ".join(cells))
        if bdeg:
            print(f"    baseline mean: {sum(v for v, _ in bdeg) / len(bdeg):.1f} C")
        else:
            print("    baseline mean: -  (the unsteered sample states no temperature)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
