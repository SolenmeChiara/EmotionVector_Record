#!/usr/bin/env python3
"""Step 5 - causal check: inject an emotion direction during generation.

A forward hook on decoder block `layer-1` (hidden_states[k] is the output of
decoder block k-1) adds  coeff * mean_norm * d_hat  to every token position of
that block's output, so the shift rides on the layer's own residual scale.
Coefficients are the ±0.3 / 0.6 / 1.0 fractions asked for in the task.

Output: results/steering_samples.md  (baseline + every emotion x coefficient)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    DATA,
    DEFAULT_MODEL,
    RESULTS,
    load_model,
    vram,
)

NEUTRAL_PROMPTS = [
    "Write tomorrow's weather forecast for a small coastal town.",
    "Describe, in a short paragraph, what happens in an office on a Tuesday morning.",
    "Write a short note to a neighbour about the building's recycling schedule.",
]


class Steerer:
    """Add coeff * vector to a decoder block's hidden-state output."""

    def __init__(self, block: torch.nn.Module, vector: torch.Tensor, coeff: float):
        self.block, self.vector, self.coeff = block, vector, float(coeff)
        self.handle = None
        self.calls = 0

    def _hook(self, _mod, _inp, out):
        self.calls += 1
        delta = self.coeff * self.vector
        if isinstance(out, tuple):
            h = out[0]
            return (h + delta.to(h.dtype).to(h.device),) + out[1:]
        return out + delta.to(out.dtype).to(out.device)

    def __enter__(self):
        self.handle = self.block.register_forward_hook(self._hook)
        return self

    def __exit__(self, *exc):
        if self.handle:
            self.handle.remove()
        self.handle = None
        return False


def generate(model, tok, prompt: str, max_new_tokens: int, seed: int) -> str:
    msgs = [{"role": "user", "content": prompt}]
    # Qwen3.5 opens every assistant turn with <think>. Left on, the whole token
    # budget goes to a planning monologue and no prose ever appears, so the
    # template's thinking switch is closed for these samples.
    try:
        text = tok.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
    except TypeError:
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    enc = tok(text, return_tensors="pt", add_special_tokens=False).to(model.device)
    torch.manual_seed(seed)
    with torch.inference_mode():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.8,
            top_p=0.95,
            pad_token_id=tok.pad_token_id or tok.eos_token_id,
        )
    return tok.decode(out[0][enc["input_ids"].shape[1] :], skip_special_tokens=True).strip()


def copy_baselines(path: str, n_prompts: int) -> dict[int, str]:
    """Lift the `**Prompt k:**` blockquotes out of an existing samples file.

    Generation is deterministic given the seed and the unsteered path has not
    changed, so a rerun would reproduce these token for token; the only reason
    they have to appear in the new file at all is that tools/compare_steering.py
    reads each sample's baseline out of the same document.
    """
    out: dict[int, str] = {}
    key: int | None = None
    buf: list[str] = []

    def commit() -> None:
        nonlocal key, buf
        if key is not None and buf:
            out[key] = "\n".join(buf).strip()
        key, buf = None, []

    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = re.match(r"\*\*Prompt (\d+):\*\*", line)
            if m:
                commit()
                idx = int(m.group(1))
                key = idx if idx <= n_prompts else None
                continue
            if line.startswith("## ") and not line.startswith("## Baseline"):
                commit()
                break
            if line.startswith("> "):
                buf.append(line[2:])
            elif line.strip() == "" and buf:
                commit()
    commit()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--directions", default=os.path.join(DATA, "directions.npz"))
    ap.add_argument("--metrics", default=os.path.join(RESULTS, "metrics.json"))
    ap.add_argument("--layers", default="", help="comma list of hidden_states indices; default = top from metrics")
    ap.add_argument("--n-layers-auto", type=int, default=2)
    ap.add_argument("--coeffs", default="-1.0,-0.6,-0.3,0.3,0.6,1.0")
    ap.add_argument("--max-new-tokens", type=int, default=170)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--which", default="dirs_raw", choices=["dirs_raw", "dirs_denoised"])
    ap.add_argument("--n-prompts", type=int, default=len(NEUTRAL_PROMPTS))
    ap.add_argument("--offload", default="", help="comma-separated module prefixes to pin to CPU")
    ap.add_argument("--8bit", dest="eightbit", action="store_true")
    ap.add_argument(
        "--labels",
        default="",
        help="comma list naming the direction rows; default = the order stored in the npz",
    )
    ap.add_argument(
        "--no-baseline",
        action="store_true",
        help="skip generating the unsteered samples (they are deterministic given the seed, "
        "so a second sweep over the same prompts would reproduce them verbatim)",
    )
    ap.add_argument(
        "--baseline-from",
        default="",
        help="copy the baseline blocks out of an existing steering_samples*.md instead of "
        "regenerating them, so the comparison tools still find a baseline in this file",
    )
    ap.add_argument("--out", default=os.path.join(RESULTS, "steering_samples.md"))
    args = ap.parse_args()

    z = np.load(args.directions, allow_pickle=True)
    dirs = z[args.which]  # [L, n_directions, hidden]
    norms = z["norms"]
    stored = [str(x) for x in z["emotions"]] if "emotions" in z.files else []
    labels = [x for x in args.labels.split(",") if x] or stored
    if len(labels) != dirs.shape[1]:
        raise SystemExit(f"{len(labels)} labels {labels} for {dirs.shape[1]} direction rows")
    if stored and labels != stored:
        raise SystemExit(f"--labels {labels} does not match the order stored in the npz: {stored}")

    if args.layers:
        layers = [int(x) for x in args.layers.split(",")]
    else:
        with open(args.metrics) as f:
            m = json.load(f)
        layers = m["steering_layers"][: args.n_layers_auto]
    coeffs = [float(x) for x in args.coeffs.split(",")]
    print(f"[plan] layers={layers} coeffs={coeffs} vectors={args.which} directions={labels}")

    prompts = NEUTRAL_PROMPTS[: args.n_prompts]
    model, tok, text_model, n_layers = load_model(
        args.model,
        load_in_8bit=args.eightbit,
        offload=[x for x in args.offload.split(",") if x] or None,
    )
    print(f"[load] {n_layers} decoder blocks; {vram('post-load')}")

    lines = [
        "# Steering samples",
        "",
        f"- model: `{args.model}`",
        f"- vectors: `{args.which}` from `{os.path.basename(args.directions)}`",
        "- hook: forward hook on decoder block `k-1` for hidden_states index `k`, added at every token position",
        "- coefficient meaning: `coeff x (mean L2 norm of that layer's pooled residual)`",
        f"- sampling: temperature 0.8, top_p 0.95, max_new_tokens {args.max_new_tokens}, seed {args.seed} (same seed for every condition)",
        "",
    ]

    os.makedirs(RESULTS, exist_ok=True)

    def flush() -> None:
        """Write what we have so far.

        A quantised 42-block model generates slowly enough that the full sweep
        runs for the better part of an hour; if it dies at minute 50 (OOM, a
        watchdog kill, a lost GPU) everything written only at the end is lost.
        Rewriting the whole buffer each time costs nothing next to a generate().
        """
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

    t0 = time.time()
    # baselines first (no hook)
    lines += ["## Baseline (no steering)", ""]
    if args.baseline_from:
        copied = copy_baselines(args.baseline_from, len(prompts))
        if len(copied) != len(prompts):
            raise SystemExit(
                f"{args.baseline_from} yielded {len(copied)} baselines, need {len(prompts)}"
            )
        note = (
            f"_copied verbatim from `{os.path.basename(args.baseline_from)}`: same prompts, same "
            "seed, same unsteered code path, so regenerating them would only burn GPU time. "
            "They are here because the comparison tools read the baseline out of this file._"
        )
        lines += [note, ""]
        for pi, p in enumerate(prompts):
            lines += [f"**Prompt {pi + 1}:** {p}", "", "> " + copied[pi + 1].replace("\n", "\n> "), ""]
        flush()
        print(f"  baselines copied from {args.baseline_from}")
    elif args.no_baseline:
        lines += ["_not generated in this run._", ""]
    else:
        for pi, p in enumerate(prompts):
            txt = generate(model, tok, p, args.max_new_tokens, args.seed + pi)
            lines += [f"**Prompt {pi + 1}:** {p}", "", "> " + txt.replace("\n", "\n> "), ""]
            flush()
            print(f"  baseline p{pi + 1} done ({time.time() - t0:.0f}s)", flush=True)

    for hs_idx in layers:
        block_idx = hs_idx - 1
        if block_idx < 0 or block_idx >= n_layers:
            lines += [f"## hidden_states {hs_idx} - SKIPPED (not a decoder block output)", ""]
            print(f"  skip hs={hs_idx}")
            continue
        block = text_model.layers[block_idx]
        scale = float(norms[hs_idx])
        lines += [
            f"## Layer hidden_states[{hs_idx}] (decoder block {block_idx}), mean residual norm {scale:.1f}",
            "",
        ]
        for ei, emo in enumerate(labels):
            v = torch.tensor(dirs[hs_idx, ei], dtype=torch.float32)
            v = v / v.norm()
            lines += [f"### {emo}", ""]
            for c in coeffs:
                vec = (v * (c * scale)).to(model.device)
                for pi, p in enumerate(prompts):
                    with Steerer(block, vec, 1.0) as st:
                        txt = generate(model, tok, p, args.max_new_tokens, args.seed + pi)
                        calls = st.calls
                    lines += [
                        f"**coeff {c:+.1f} x norm | prompt {pi + 1}** (hook fired {calls}x)",
                        "",
                        "> " + txt.replace("\n", "\n> "),
                        "",
                    ]
                flush()
                print(f"  hs{hs_idx} {emo} coeff {c:+.1f} done ({time.time() - t0:.0f}s)", flush=True)

    lines += ["", f"_generated in {time.time() - t0:.0f}s; {vram('final')}_", ""]
    flush()
    print(f"-> {args.out}")
    print(vram("final"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
