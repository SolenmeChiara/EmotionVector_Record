#!/usr/bin/env python3
"""Phase seven, GPU side - steer with the tickle (and itch) direction, then token maps.

Windows-native only (.venv-win). Never run this under WSL.

Part 1, steering. Same hook, same generate(), same sampling as phase three
(core/steer.py: forward hook on decoder block k-1 for hidden_states[k], added at
every position, coeff x the layer's mean pooled-residual norm; temperature 0.8,
top_p 0.95, max_new_tokens 150, enable_thinking=False, seed + prompt index).
Only the injected vector changes. Prompts 1-2 are phase three's two prompts
(forecast, office); prompt 3 is a new plain explanatory task (cooking rice),
added to see whether the direction leaks into instructional prose.

Order of work is by priority, so a watchdog kill keeps what matters most:
all baselines -> tickle (every seed) -> itch -> happy / pain controls.
Everything is flushed to JSON + markdown after every single generation.

Part 2, token maps (optional, --token-texts). One forward pass per passage, no
hook; per-token partial projections at hidden_states[17] onto happy / pain /
warm (phase one and three directions, each with its own corpus centre and
generic axis) and tickle / itch (this phase, with this corpus's centre/axis).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import DATA, RESULTS, load_model, vram
from dir_cosine import generic_axis
from steer import NEUTRAL_PROMPTS, Steerer, generate

PROMPTS = [
    NEUTRAL_PROMPTS[0],  # forecast (phase one / three prompt 1)
    NEUTRAL_PROMPTS[1],  # office  (phase one / three prompt 2)
    "Explain how to cook a pot of rice on the stove.",
]

# (label, directions file, row name, acts file, groups stored in acts, targets)
DIR_SOURCES = {
    "tickle": ("directions_sens_tickle.npz", "tickle"),
    "itch": ("directions_sens_tickle.npz", "itch"),
    "happy": ("directions.npz", "happy"),
    "pain": ("directions_sens.npz", "pain"),
    "warm": ("directions_sens.npz", "warm"),
}
ACTS_FOR = {
    "directions_sens_tickle.npz": ("acts_sens_tickle.npz", ["warm", "cold", "pain", "neutral", "tickle", "itch"],
                                   ["warm", "cold", "pain", "tickle", "itch"]),
    "directions.npz": ("acts.npz", ["happy", "sad", "angry", "fearful", "neutral"], ["happy", "sad", "angry", "fearful"]),
    "directions_sens.npz": ("acts_sens.npz", ["warm", "cold", "pain", "neutral"], ["warm", "cold", "pain"]),
}


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def load_dir(label: str, layer: int, which: str) -> dict:
    fname, row = DIR_SOURCES[label]
    z = np.load(os.path.join(DATA, fname), allow_pickle=True)
    names = [str(x) for x in z["emotions"]]
    d = unit(z[which][layer, names.index(row)].astype(np.float64))
    acts, groups, targets = ACTS_FOR[fname]
    ga = generic_axis(os.path.join(DATA, acts), groups, targets, 8, 7)[layer].astype(np.float64)
    a = unit(ga)
    return {
        "label": label,
        "file": fname,
        "d": d,
        "norm": float(z["norms"][layer]),
        "grand": z["grand_means"][layer].astype(np.float64),
        "axis": a,
        "d_perp": unit(d - a * float(d @ a)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3.5-4B")
    ap.add_argument("--layer", type=int, default=17)
    ap.add_argument("--which", default="dirs_raw", choices=["dirs_raw", "dirs_denoised"])
    ap.add_argument("--coeffs", default="0.3,0.6,1.0")
    ap.add_argument("--seeds", default="1234,2234,3234,4234")
    ap.add_argument("--steer", default="tickle,itch,happy,pain", help="directions to steer with, in priority order")
    ap.add_argument("--n-prompts", type=int, default=len(PROMPTS))
    ap.add_argument("--max-new-tokens", type=int, default=150)
    ap.add_argument("--json-out", default=os.path.join(RESULTS, "steering_tickle_itch.json"))
    ap.add_argument("--md-dir", default=RESULTS, help="writes steering_samples_<label>.md here")
    ap.add_argument("--token-texts", default="", help="JSON list of {id, text}; empty = skip part 2")
    ap.add_argument("--token-out", default=os.path.join(RESULTS, "tickle_tokenmaps.json"))
    ap.add_argument("--skip-steer", action="store_true")
    args = ap.parse_args()

    k = args.layer
    coeffs = [float(x) for x in args.coeffs.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")]
    labels = [x for x in args.steer.split(",") if x]
    prompts = PROMPTS[: args.n_prompts]
    dirs = {lab: load_dir(lab, k, args.which) for lab in set(labels) | {"tickle", "itch", "happy", "pain", "warm"}}
    for lab, r in dirs.items():
        print(f"[dir] {lab:<7} from {r['file']:<28} norm[{k}]={r['norm']:.3f} load_on_axis={float(r['d'] @ r['axis']):+.3f}")

    t_load = time.time()
    model, tok, text_model, n_layers = load_model(args.model)
    print(f"[load] {n_layers} blocks in {time.time() - t_load:.1f}s; {vram('post-load')}", flush=True)
    block = text_model.layers[k - 1]

    records: list[dict] = []
    if os.path.exists(args.json_out) and not args.skip_steer:
        print(f"[resume] {args.json_out} exists and will be overwritten")

    def flush() -> None:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "model": args.model,
                    "layer": k,
                    "which": args.which,
                    "sampling": {"temperature": 0.8, "top_p": 0.95, "max_new_tokens": args.max_new_tokens,
                                 "seed_rule": "seed + prompt_index (0-based)", "enable_thinking": False},
                    "prompts": prompts,
                    "norms": {lab: dirs[lab]["norm"] for lab in dirs},
                    "records": records,
                },
                fh,
                ensure_ascii=False,
                indent=1,
            )
        by_label: dict[str, list[dict]] = {}
        for r in records:
            by_label.setdefault(r["direction"], []).append(r)
        base = {(r["seed"], r["prompt"]): r["text"] for r in records if r["direction"] == "baseline"}
        for lab in labels:
            rows = by_label.get(lab, [])
            out = [
                f"# Steering samples - {lab}",
                "",
                f"- model: `{args.model}`, bf16, Windows native",
                (f"- vector: `{args.which}` row `{lab}` from `{dirs[lab]['file']}`, hidden_states[{k}] (decoder block {k - 1}), "
                 f"mean residual norm {dirs[lab]['norm']:.3f}"),
                "- hook: added at every token position; coefficient = coeff x that norm",
                f"- sampling: temperature 0.8, top_p 0.95, max_new_tokens {args.max_new_tokens}, seed + prompt index, thinking off",
                f"- seeds: {seeds}; coefficients: {coeffs}",
                "",
            ]
            for s in seeds:
                out += [f"## seed {s}", ""]
                for pi, p in enumerate(prompts):
                    out += [f"### prompt {pi + 1}: {p}", ""]
                    if (s, pi + 1) in base:
                        out += ["**baseline (no steering)**", "", "> " + base[(s, pi + 1)].replace("\n", "\n> "), ""]
                    for r in rows:
                        if r["seed"] == s and r["prompt"] == pi + 1:
                            out += [f"**{lab} {r['coeff']:+.1f} x norm** ({r['n_tokens']} tokens, hook fired {r['hook_calls']}x)",
                                    "", "> " + r["text"].replace("\n", "\n> "), ""]
            with open(os.path.join(args.md_dir, f"steering_samples_{lab}.md"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(out))

    def run_one(label: str, coeff: float, seed: int, pi: int) -> None:
        t = time.time()
        if label == "baseline":
            txt = generate(model, tok, prompts[pi], args.max_new_tokens, seed + pi)
            calls = 0
        else:
            vec = torch.tensor(dirs[label]["d"] * coeff * dirs[label]["norm"], dtype=torch.float32).to(model.device)
            with Steerer(block, vec, 1.0) as st:
                txt = generate(model, tok, prompts[pi], args.max_new_tokens, seed + pi)
                calls = st.calls
        n_tok = len(tok(txt, add_special_tokens=False)["input_ids"])
        records.append({"direction": label, "coeff": coeff, "seed": seed, "prompt": pi + 1,
                        "text": txt, "n_tokens": n_tok, "hook_calls": calls, "secs": round(time.time() - t, 1)})
        flush()

    t0 = time.time()
    if not args.skip_steer:
        for s in seeds:
            for pi in range(len(prompts)):
                run_one("baseline", 0.0, s, pi)
        print(f"  baselines done ({time.time() - t0:.0f}s) {vram('run')}", flush=True)
        for lab in labels:
            for s in seeds:
                for c in coeffs:
                    for pi in range(len(prompts)):
                        run_one(lab, c, s, pi)
                print(f"  {lab} seed {s} done ({time.time() - t0:.0f}s)", flush=True)
        print(f"[steer] {len(records)} generations in {time.time() - t0:.0f}s; {vram('steer-final')}", flush=True)

    if args.token_texts:
        with open(args.token_texts, encoding="utf-8") as fh:
            texts = json.load(fh)
        names = ["happy", "pain", "warm", "tickle", "itch"]
        out = {"layer": k, "which": args.which, "mode": "partial", "directions": names, "passages": []}
        with torch.inference_mode():
            for item in texts:
                enc = tok(item["text"], return_tensors="pt", add_special_tokens=True, return_offsets_mapping=True)
                offsets = enc.pop("offset_mapping")[0].tolist()
                enc = {kk: v.to(model.device) for kk, v in enc.items()}
                hs = model(**enc, output_hidden_states=True, use_cache=False).hidden_states[k][0].float().cpu().numpy()
                ids = enc["input_ids"][0].tolist()
                toks = [item["text"][a:b] if b > a else tok.decode([i]) for (a, b), i in zip(offsets, ids)]
                proj = {}
                for nme in names:
                    r = dirs[nme]
                    proj[nme] = [round(float(x), 4) for x in (hs.astype(np.float64) - r["grand"]) @ r["d_perp"]]
                out["passages"].append({"id": item["id"], "text": item["text"], "tokens": toks, "partial": proj})
                print(f"  tokenmap {item['id']}: {len(toks)} tokens", flush=True)
        with open(args.token_out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print(f"-> {args.token_out}")

    print(f"[done] total {time.time() - t0:.0f}s; peak_alloc={torch.cuda.max_memory_allocated() / 2**30:.2f}GiB; {vram('final')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
