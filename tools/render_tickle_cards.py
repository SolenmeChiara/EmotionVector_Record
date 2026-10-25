#!/usr/bin/env python3
"""Phase seven - render the token-level cards used in the README (CPU only).

Reads results/tickle_tokenmaps.json (written by tools/tickle_steer.py, part 2)
and draws one card per hand-written passage: every token coloured by its
partial projection at hidden_states[17] onto one direction per row. Orange steps
mean the token runs along the direction ("lit up"), blue steps mean it runs
against it ("pushed against"). The colour scale is quantile-based per direction,
pooled over the three hand-written passages in that JSON (75/90/95/99th
percentiles on the positive side, 25/10/5/1st on the negative side), the same
idea as tools/render_heatmaps.py, so depth is comparable across passages.

--selfread also draws a third card: the tickle +1.0 / seed 3234 / forecast reply
(results/steering_tickle_itch.json) read back token by token by the UNSTEERED
model, produced with

  tools/tickle_steer.py --skip-steer --token-texts results/tickle_selfread_texts.json \
      --token-out results/tickle_selfread_tokenmaps.json

That passage is coloured on the SAME scale, still calibrated on the three
hand-written passages only; it is not added to the quantile pool.

Usage:
  python tools/render_tickle_cards.py [--tokenmaps PATH] [--out-dir DIR] [--selfread [PATH]]

Defaults: results/tickle_tokenmaps.json -> images/tickle_card_fingers.png and
images/tickle_card_itch.png (+ images/tickle_card_selfread.png with --selfread,
reading results/tickle_selfread_tokenmaps.json). Needs numpy and Pillow. Uses
DejaVu Sans if it can find it (system fonts, or the copy bundled with
matplotlib); otherwise falls back to Pillow's default font, which still renders
but will not match the published images pixel for pixel.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TOKENMAPS = os.path.join(ROOT, "results", "tickle_tokenmaps.json")
DEFAULT_SELFREAD = os.path.join(ROOT, "results", "tickle_selfread_tokenmaps.json")

POS = ["#f3e3c3", "#e8c48a", "#d79a4a", "#b8641c"]  # ochre steps
NEG = ["#dde3ee", "#b9c4da", "#8c9cc0", "#5b6b99"]  # slate-indigo steps
BG, INK, MUTE, RULE = "#fbfaf7", "#1d1c1a", "#77736b", "#d8d4cc"
W, PAD, LH = 1080, 48, 46

CALIB: list[dict] = []  # passages the colour scale is calibrated on
P: dict[str, dict] = {}  # every passage that can be drawn, by id


def scale(direction):
    """Quantile scale per direction, pooled over the calibration passages."""
    v = np.concatenate([np.array(p["partial"][direction]) for p in CALIB])
    pos = np.percentile(v, [75, 90, 95, 99])
    neg = np.percentile(v, [25, 10, 5, 1])
    return pos, neg


def color(x, pos, neg):
    for i in range(3, -1, -1):
        if x >= pos[i]:
            return POS[i], (i >= 2)
        if x <= neg[i]:
            return NEG[i], (i >= 2)
    return None, False


def _font_candidates(bold: bool) -> list[str]:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    cands = [
        os.path.join("/usr/share/fonts/truetype/dejavu", name),  # Debian / Ubuntu
        os.path.join("/usr/share/fonts/dejavu", name),  # Fedora / Arch
        name,  # let Pillow search the system font directories
    ]
    try:  # matplotlib bundles DejaVu Sans; it is optional here
        import matplotlib
    except ImportError:
        return cands
    cands.append(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", name))
    return cands


def load_font(size: int, bold: bool = False):
    for path in _font_candidates(bold):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    print(f"[font] DejaVu Sans{' Bold' if bold else ''} not found; using Pillow's default font", file=sys.stderr)
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


FONT = load_font(30)
BOLD = load_font(34, bold=True)
SMALL = load_font(24)


def panel(draw, y, pid, direction, label):
    pos, neg = scale(direction)
    p = P[pid]
    draw.text((PAD, y), label, font=BOLD, fill=INK)
    y += 52
    x = PAD
    for tok, val in zip(p["tokens"], p["partial"][direction]):
        t = tok.replace("\n", " ")
        lead = t.startswith(" ")
        word = t.strip()
        if not word:
            x += 9
            continue
        if lead:
            x += 9
        w = draw.textlength(word, font=FONT)
        if x + w > W - PAD:
            x = PAD
            y += LH
        c, dark = color(val, pos, neg)
        if c:
            draw.rounded_rectangle((x - 3, y - 2, x + w + 3, y + 38), radius=6, fill=c)
        draw.text((x, y), word, font=FONT, fill="#ffffff" if dark else INK)
        x += w
    y += LH + 20
    draw.line((PAD, y, W - PAD, y), fill=RULE, width=2)
    return y + 28


def card(pid, rows, title, path):
    img = Image.new("RGB", (W, 4000), BG)
    dr = ImageDraw.Draw(img)
    y = PAD
    dr.text((PAD, y), title, font=BOLD, fill=INK)
    y += 50
    dr.text((PAD, y), "Qwen3.5-4B · layer 17 · partial projection", font=SMALL, fill=MUTE)
    y += 40
    # legend
    lx = PAD
    for c in reversed(NEG):
        dr.rectangle((lx, y, lx + 34, y + 22), fill=c)
        lx += 36
    dr.text((lx + 8, y - 4), "pushed against", font=SMALL, fill=MUTE)
    lx += 200
    for c in POS:
        dr.rectangle((lx, y, lx + 34, y + 22), fill=c)
        lx += 36
    dr.text((lx + 8, y - 4), "lit up", font=SMALL, fill=MUTE)
    y += 56
    dr.line((PAD, y, W - PAD, y), fill=RULE, width=2)
    y += 28
    for direction, label in rows:
        y = panel(dr, y, pid, direction, label)
    img.crop((0, 0, W, y + 10)).save(path)
    print(f"-> {path} (height {y + 10})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tokenmaps", default=DEFAULT_TOKENMAPS,
                    help="hand-written passages; also the colour-scale calibration set")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "images"))
    ap.add_argument("--selfread", nargs="?", const=DEFAULT_SELFREAD, default=None, metavar="PATH",
                    help=f"also draw the self-read card (default data: {os.path.relpath(DEFAULT_SELFREAD, ROOT)})")
    args = ap.parse_args()

    with open(args.tokenmaps, encoding="utf-8") as fh:
        CALIB.extend(json.load(fh)["passages"])
    P.update({p["id"]: p for p in CALIB})
    os.makedirs(args.out_dir, exist_ok=True)

    rows3 = [("tickle", "tickle"), ("happy", "happy"), ("pain", "pain")]
    card("scene_fingers", rows3, "Being tickled, read three ways",
         os.path.join(args.out_dir, "tickle_card_fingers.png"))
    card("scene_itch", [("itch", "itch"), ("tickle", "tickle"), ("pain", "pain")], "An itch, read three ways",
         os.path.join(args.out_dir, "tickle_card_itch.png"))

    if args.selfread:
        with open(args.selfread, encoding="utf-8") as fh:
            sp = json.load(fh)["passages"][0]
        if "selfread" in P:
            raise SystemExit("passage id 'selfread' already present in the calibration set")
        P["selfread"] = sp  # drawable, but NOT part of CALIB: the scale stays on the hand-written passages
        card("selfread", rows3, "The model reads its own tickled reply",
             os.path.join(args.out_dir, "tickle_card_selfread.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
