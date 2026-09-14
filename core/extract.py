#!/usr/bin/env python3
"""Step 1 - extract residual-stream activations for every story, all layers.

For each story: one forward pass with output_hidden_states=True, then mean-pool
the *second half* of the story's own tokens at every layer (the paper pools from
token 50 onward on much longer stories; on 60-110 word passages the back half is
the same idea - skip the opening where the topic is still being set up).

Writes data/acts.npz:
    acts   float32 [n_layers+1, n_stories, hidden]
    labels int32   [n_stories]   index into GROUPS
    ids    str     [n_stories]
    norms  float32 [n_layers+1]  mean L2 norm of the pooled residual per layer
                                 (the scale that steering coefficients ride on)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    DATA,
    DEFAULT_MODEL,
    GROUPS,
    load_model,
    load_stories,
    vram,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default=os.path.join(DATA, "acts.npz"))
    ap.add_argument("--pool-from", type=float, default=0.5, help="pool tokens from this fraction onward")
    ap.add_argument("--8bit", dest="eightbit", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="smoke test: keep only N stories per group")
    ap.add_argument(
        "--offload",
        default="",
        help="comma-separated module prefixes to pin to CPU (e.g. Gemma-4's PLE table and towers)",
    )
    ap.add_argument("--max-memory-gpu", default="", help="e.g. 12GiB; switches to accelerate auto-split")
    ap.add_argument(
        "--groups",
        default="",
        help="comma list of story groups (default: the four emotions + neutral). "
        "The label column indexes into THIS list, and the list is stored in the "
        "npz, so downstream tools never have to guess the ordering.",
    )
    args = ap.parse_args()

    groups = [g for g in args.groups.split(",") if g] or GROUPS

    print(f"[env] torch {torch.__version__} cuda={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"[env] device {torch.cuda.get_device_name(0)} cap={torch.cuda.get_device_capability(0)}")
    print(vram("pre-load"))

    t0 = time.time()
    model, tok, _text_model, n_layers = load_model(
        args.model,
        load_in_8bit=args.eightbit,
        offload=[s for s in args.offload.split(",") if s] or None,
        max_memory_gpu=args.max_memory_gpu or None,
    )
    # hf_device_map is the authoritative placement record; offloaded parameters
    # report device "meta" because accelerate keeps them behind a hook.
    hfmap = getattr(model, "hf_device_map", None) or {}
    devs = sorted({str(v) for v in hfmap.values()}) or sorted({str(p.device) for p in model.parameters()})
    cpu_modules = sorted(k for k, v in hfmap.items() if str(v) == "cpu")
    print(f"[load] devices in use: {devs}" + (f"; on cpu: {cpu_modules}" if cpu_modules else ""))
    print(f"[load] {args.model}: {n_layers} decoder layers in {time.time() - t0:.1f}s")
    print(vram("post-load"))

    stories = load_stories(groups)
    if args.limit:
        kept, seen = [], {}
        for s in stories:
            seen[s["group"]] = seen.get(s["group"], 0) + 1
            if seen[s["group"]] <= args.limit:
                kept.append(s)
        stories = kept
    print(f"[data] {len(stories)} stories across {len(groups)} groups: {groups}")

    hidden = None
    acc: list[list[np.ndarray]] = None  # type: ignore[assignment]
    labels, ids, tok_counts = [], [], []

    t0 = time.time()
    with torch.inference_mode():
        for i, s in enumerate(stories):
            enc = tok(s["text"], return_tensors="pt", add_special_tokens=True)
            enc = {k: v.to(model.device) for k, v in enc.items()}
            out = model(**enc, output_hidden_states=True, use_cache=False)
            hs = out.hidden_states  # tuple: embeddings + one per decoder layer
            if acc is None:
                hidden = hs[0].shape[-1]
                acc = [[] for _ in range(len(hs))]
                print(f"[shape] {len(hs)} hidden_states tensors, hidden={hidden}")
            T = hs[0].shape[1]
            start = min(int(T * args.pool_from), max(T - 1, 0))
            tok_counts.append(T)
            for li, h in enumerate(hs):
                acc[li].append(h[0, start:, :].float().mean(0).cpu().numpy())
            labels.append(groups.index(s["group"]))
            ids.append(s["id"])
            del out, hs
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(stories)}  {vram('run')}")

    acts = np.stack([np.stack(layer) for layer in acc]).astype(np.float32)
    norms = np.linalg.norm(acts, axis=2).mean(axis=1).astype(np.float32)
    print(f"[done] acts {acts.shape} in {time.time() - t0:.1f}s")
    print(vram("final"))

    np.savez_compressed(
        args.out,
        acts=acts,
        labels=np.array(labels, dtype=np.int32),
        ids=np.array(ids),
        norms=norms,
        groups=np.array(groups),
        token_counts=np.array(tok_counts, dtype=np.int32),
    )
    meta = {
        "model": args.model,
        "groups": groups,
        "n_layers_decoder": n_layers,
        "n_hidden_states": int(acts.shape[0]),
        "hidden": int(acts.shape[2]),
        "n_stories": int(acts.shape[1]),
        "pool_from_fraction": args.pool_from,
        "mean_tokens": float(np.mean(tok_counts)),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "peak_alloc_GiB": round(torch.cuda.max_memory_allocated() / 2**30, 2)
        if torch.cuda.is_available()
        else None,
        "layer_mean_norms": [round(float(x), 3) for x in norms],
        "eightbit": args.eightbit,
        "offload": args.offload or None,
        "max_memory_gpu": args.max_memory_gpu or None,
        "param_devices": devs,
        "cpu_modules": cpu_modules,
    }
    # Derive the metadata filename from --out, or a second model's run silently
    # overwrites the first model's record.
    meta_path = os.path.splitext(args.out)[0] + "_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"-> {args.out}\n-> {meta_path}")
    print(json.dumps({k: v for k, v in meta.items() if k != "layer_mean_norms"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
