#!/usr/bin/env python3
"""Windows-side load smoke test: does the real checkpoint actually come up?

Everything before this script only proved that CUDA and the bitsandbytes kernel
work on a toy nn.Linear. This one loads the real weights, runs one forward with
output_hidden_states, runs one short generate, and prints the VRAM numbers, so
the steering run afterwards is not the first time the model has ever been on
this GPU.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))
from common import load_model, vram


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/gemma-4-E4B-it")
    ap.add_argument("--8bit", dest="eightbit", action="store_true")
    ap.add_argument("--max-new-tokens", type=int, default=24)
    args = ap.parse_args()

    print(f"torch {torch.__version__}  cuda_build {torch.version.cuda}  available={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"device {torch.cuda.get_device_name(0)}  capability {torch.cuda.get_device_capability(0)}")
    print(f"HF_HOME={os.environ.get('HF_HOME')}  XET_DISABLED={os.environ.get('HF_HUB_DISABLE_XET')}")
    print(vram("pre-load"), flush=True)

    t0 = time.time()
    model, tok, _text_model, n_layers = load_model(args.model, load_in_8bit=args.eightbit)
    print(f"[load] {n_layers} decoder blocks in {time.time() - t0:.0f}s")
    print(vram("post-load"), flush=True)

    # --- one forward with hidden states -------------------------------------
    text = "The student walked home through the rain, thinking about the week."
    enc = tok(text, return_tensors="pt").to(model.device)
    t1 = time.time()
    with torch.inference_mode():
        out = model(**enc, output_hidden_states=True)
    hs = out.hidden_states
    print(f"[fwd] {time.time() - t1:.2f}s  n_hidden_states={len(hs)}  hs[1].shape={tuple(hs[1].shape)}")
    norms = [float(h[0].float().norm(dim=-1).mean()) for h in hs]
    print(f"[fwd] residual mean-norm  hs0={norms[0]:.1f}  hs{len(hs) // 2}={norms[len(hs) // 2]:.1f}  hs{len(hs) - 1}={norms[-1]:.1f}")
    print(vram("post-forward"), flush=True)

    # --- one short generate, with the same chat-template path steer.py uses ---
    msgs = [{"role": "user", "content": "Describe, in one sentence, a quiet morning."}]
    try:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        print("[chat] enable_thinking=False accepted")
    except TypeError:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        print("[chat] enable_thinking not supported by this template; using plain call")
    genc = tok(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
    torch.manual_seed(1234)
    t2 = time.time()
    with torch.inference_mode():
        g = model.generate(
            **genc,
            max_new_tokens=args.max_new_tokens,
            do_sample=True,
            temperature=0.8,
            top_p=0.95,
            pad_token_id=tok.pad_token_id or tok.eos_token_id,
        )
    dt = time.time() - t2
    txt = tok.decode(g[0][genc["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    print(f"[gen] {args.max_new_tokens} tokens in {dt:.1f}s ({args.max_new_tokens / dt:.1f} tok/s)")
    print(f"[gen] -> {txt!r}")
    print(vram("final"))

    # rough projection for the steering run
    print(f"[est] 150-token sample ~= {150 / (args.max_new_tokens / dt):.0f}s; 98 samples ~= {98 * 150 / (args.max_new_tokens / dt) / 60:.0f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
