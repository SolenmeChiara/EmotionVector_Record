#!/usr/bin/env python3
"""Phase five step 1 (GPU) - generate replies under four system-prompt tiers and
project every generated token onto the seven directions.

Procedure per cell (tier x message x seed):

  1. build the chat prompt with `apply_chat_template` (system + user,
     `enable_thinking=False` - Qwen3.5 otherwise spends the whole budget on a
     planning monologue, see core/steer.py),
  2. sample a reply (temperature 0.8, top_p 0.95, max_new_tokens 200),
  3. re-run one forward pass over `prompt_ids + reply_ids` and read
     `hidden_states[17]` at the reply positions.

Step 3 reproduces exactly the states the model was in while writing those tokens
(same ids, same left context, no sampling involved), and it is the only way to get
all positions at once without hooking generate().  The projection maths is lifted
verbatim from tools/token_project.py - same `load_directions`, same four modes,
same per-corpus grand mean and generic axis - so phase four's colour scale and
phase five's numbers are in the same units.

The system prompt sits in the context of every reply token, so the tier effect
measured here is "the residual stream while writing this reply, under this
instruction", which is the quantity the question asks about.  It is not a claim
that the reply *text* alone carries the signal; see the report's confound note.

Writes, as it goes:
  results/refusal_maps/<id>.json      per-reply token map (render_heatmaps schema)
  results/refusal_replies.md          all replies, full text
  results/refusal_meanvecs.npz        per-reply mean residual at the layer
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
from common import RESULTS, load_model, vram
from refusal_prompts import MESSAGES, SYSTEM_PROMPTS, TIERS
from token_project import MODES, load_directions


def build_prompt(tok, system: str, user: str) -> str:
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        return tok.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
    except TypeError:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)


def incremental_pieces(tok, ids: list[int]) -> list[str]:
    """Display string per token id, by differencing successive full decodes.

    Decoding ids one at a time turns a byte-level piece that splits a multi-byte
    character into a replacement glyph.  Differencing `decode(ids[:i+1])` against
    `decode(ids[:i])` keeps the text exact: the first half of a split character
    contributes "" and the second contributes the whole character.  O(n^2) in a
    200-token reply is microseconds.
    """
    out, prev = [], ""
    for i in range(len(ids)):
        cur = tok.decode(ids[: i + 1], skip_special_tokens=False)
        out.append(cur[len(prev):] if cur.startswith(prev) else tok.decode([ids[i]]))
        prev = cur
    return out


def ttr(text: str) -> float:
    words = [w.strip(".,!?;:\"'()-").lower() for w in text.split()]
    words = [w for w in words if w]
    return round(len(set(words)) / len(words), 4) if words else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3.5-4B")
    ap.add_argument("--layer", type=int, default=17)
    ap.add_argument("--which", default="dirs_raw", choices=["dirs_raw", "dirs_denoised"])
    ap.add_argument("--seeds", default="1234,2234")
    ap.add_argument("--tiers", default=",".join(TIERS))
    ap.add_argument("--max-new-tokens", type=int, default=200)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--outdir", default=os.path.join(RESULTS, "refusal_maps"))
    ap.add_argument("--replies-out", default=os.path.join(RESULTS, "refusal_replies.md"))
    ap.add_argument("--vecs-out", default=os.path.join(RESULTS, "refusal_meanvecs.npz"))
    args = ap.parse_args()

    seeds = [int(x) for x in args.seeds.split(",") if x]
    tiers = [x for x in args.tiers.split(",") if x]
    for t in tiers:
        if t not in SYSTEM_PROMPTS:
            raise SystemExit(f"unknown tier {t!r}; have {list(SYSTEM_PROMPTS)}")
    os.makedirs(args.outdir, exist_ok=True)

    dirs = load_directions(args.layer, args.which)
    names = [r["name"] for r in dirs]
    D = np.stack([r["d"] for r in dirs])
    Dp = np.stack([r["d_perp"] for r in dirs])
    G = np.stack([r["grand"] for r in dirs])

    print(f"[env] torch {torch.__version__} cuda={torch.cuda.is_available()}")
    print(vram("pre-load"))
    t0 = time.time()
    model, tok, _tm, n_layers = load_model(args.model)
    print(f"[load] {args.model}: {n_layers} blocks in {time.time() - t0:.1f}s; {vram('post-load')}")

    eos_ids = {int(i) for i in ([tok.eos_token_id] if tok.eos_token_id is not None else [])}
    for name in ("<|im_end|>", "<|endoftext|>"):
        i = tok.convert_tokens_to_ids(name)
        if isinstance(i, int) and i >= 0:
            eos_ids.add(i)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    print(f"[gen] stop ids {sorted(eos_ids)}, pad {pad_id}")

    # System-prompt token lengths: the tiers are not length-matched and the number
    # belongs in the report rather than in a footnote nobody can check.
    sys_len = {t: len(tok(SYSTEM_PROMPTS[t], add_special_tokens=False)["input_ids"]) for t in tiers}
    print("[gen] system prompt tokens: " + ", ".join(f"{k}={v}" for k, v in sys_len.items()))

    md = [
        "# Phase five - replies to eight declarations of love under four system-prompt tiers",
        "",
        f"- model `{args.model}`, bf16, Windows native; projections at `hidden_states[{args.layer}]`",
        (f"- sampling: temperature {args.temperature}, top_p {args.top_p}, "
         f"max_new_tokens {args.max_new_tokens}, seeds {seeds}"),
        "- system prompt lengths in tokens: "
        + ", ".join(f"`{k}`={v}" for k, v in sys_len.items()),
        ("- `mean` / `top10%` below are **partial** projections (the corpus generic axis "
         "projected out of each direction), averaged over the reply's generated tokens only."),
        "",
    ]
    recs_meta: list[dict] = []
    vecs: list[np.ndarray] = []

    def flush_md() -> None:
        with open(args.replies_out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md))

    n_total = len(tiers) * len(MESSAGES) * len(seeds)
    done = 0
    tgen = time.time()
    for tier in tiers:
        md += [f"## tier: {tier}", "", "```", SYSTEM_PROMPTS[tier], "```", ""]
        flush_md()
        for msg in MESSAGES:
            for seed in seeds:
                rid = f"{tier}__{msg['id']}__s{seed}"
                text = build_prompt(tok, SYSTEM_PROMPTS[tier], msg["text"])
                enc = tok(text, return_tensors="pt", add_special_tokens=False)
                prompt_ids = enc["input_ids"][0].tolist()
                enc = {k: v.to(model.device) for k, v in enc.items()}
                torch.manual_seed(seed)
                with torch.inference_mode():
                    out = model.generate(
                        **enc,
                        max_new_tokens=args.max_new_tokens,
                        do_sample=True,
                        temperature=args.temperature,
                        top_p=args.top_p,
                        pad_token_id=pad_id,
                    )
                gen_ids = out[0][len(prompt_ids):].tolist()
                hit_eos = any(i in eos_ids for i in gen_ids)
                # keep only the leading run before the first stop token, so nothing
                # after an early <|im_end|> is scored
                cut = len(gen_ids)
                for k, i in enumerate(gen_ids):
                    if i in eos_ids:
                        cut = k
                        break
                reply_ids = gen_ids[:cut]
                reply = tok.decode(reply_ids, skip_special_tokens=True).strip()
                if not reply_ids:
                    print(f"  [{rid}] EMPTY reply, skipped")
                    md += [f"**{msg['id']} seed {seed}** - empty reply", ""]
                    done += 1
                    continue

                full = torch.tensor([prompt_ids + reply_ids], device=model.device)
                with torch.inference_mode():
                    o2 = model(input_ids=full, output_hidden_states=True, use_cache=False)
                    H = o2.hidden_states[args.layer][0, len(prompt_ids):].float().cpu().numpy()
                del o2
                H = H.astype(np.float64)

                mean_t = H.mean(0, keepdims=True)
                proj = {
                    "raw": np.stack([(H - G[i]) @ D[i] for i in range(len(dirs))], axis=0),
                    "center": ((H - mean_t) @ D.T).T,
                    "partial": np.stack([(H - G[i]) @ Dp[i] for i in range(len(dirs))], axis=0),
                    "center_partial": ((H - mean_t) @ Dp.T).T,
                }
                k = max(1, H.shape[0] // 10)
                topdec = {
                    names[i]: round(float(np.sort(proj["partial"][i])[-k:].mean()), 4)
                    for i in range(len(dirs))
                }
                pmean = {
                    m: {names[i]: round(float(proj[m][i].mean()), 4) for i in range(len(dirs))}
                    for m in MODES
                }
                pieces = incremental_pieces(tok, reply_ids)

                rec = {
                    "id": rid,
                    "family": tier,
                    "title": f"{tier} / {msg['id']} / seed {seed}",
                    "note": f"{msg['style']} - reply under the `{tier}` system prompt, seed {seed}",
                    "expect": tier,
                    "words": len(reply.split()),
                    "text": reply,
                    "layer": args.layer,
                    "which": args.which,
                    "model": args.model,
                    "directions": names,
                    "tokens": pieces,
                    "token_ids": reply_ids,
                    "token_norm": [round(float(x), 3) for x in np.linalg.norm(H, axis=1)],
                    "n_tokens": len(reply_ids),
                    "proj": {m: [[round(float(x), 4) for x in row] for row in proj[m]] for m in MODES},
                    "passage_mean": pmean,
                    "cell": {
                        "tier": tier, "msg_id": msg["id"], "style": msg["style"], "seed": seed,
                        "prompt_tokens": len(prompt_ids), "sys_tokens": sys_len[tier],
                        "hit_eos": bool(hit_eos), "truncated": not hit_eos,
                        "ttr": ttr(reply), "top_decile_partial": topdec,
                    },
                }
                with open(os.path.join(args.outdir, f"{rid}.json"), "w", encoding="utf-8") as fh:
                    json.dump(rec, fh, ensure_ascii=False)

                vecs.append(H.mean(0))
                recs_meta.append({
                    "id": rid, "tier": tier, "msg_id": msg["id"], "seed": seed,
                    "n_tokens": len(reply_ids), "truncated": not hit_eos,
                })

                order = sorted(pmean["partial"].items(), key=lambda kv: -kv[1])
                md += [
                    f"**{msg['id']} · seed {seed}** — {len(reply_ids)} tokens, "
                    f"{len(reply.split())} words, TTR {ttr(reply):.3f}"
                    + ("" if hit_eos else ", **truncated at the token cap**"),
                    "",
                    "> " + reply.replace("\n", "\n> "),
                    "",
                    "mean(partial): " + ", ".join(f"`{k2} {v2:+.3f}`" for k2, v2 in order),
                    "",
                    "top-decile(partial): "
                    + ", ".join(
                        f"`{k2} {v2:+.3f}`"
                        for k2, v2 in sorted(topdec.items(), key=lambda kv: -kv[1])
                    ),
                    "",
                ]
                flush_md()
                done += 1
                print(
                    f"  [{done:2d}/{n_total}] {rid:44s} T={len(reply_ids):3d} "
                    f"top=" + ", ".join(f"{k2} {v2:+.3f}" for k2, v2 in order[:3]),
                    flush=True,
                )

    md += ["", f"_generated in {time.time() - tgen:.0f}s; {vram('final')}_", ""]
    flush_md()
    np.savez_compressed(
        args.vecs_out,
        vecs=np.stack(vecs).astype(np.float32),
        ids=np.array([r["id"] for r in recs_meta]),
        tiers=np.array([r["tier"] for r in recs_meta]),
        msg_ids=np.array([r["msg_id"] for r in recs_meta]),
        seeds=np.array([r["seed"] for r in recs_meta]),
        layer=np.array(args.layer),
    )
    print(f"-> {args.replies_out}\n-> {args.vecs_out}\n-> {args.outdir}/*.json")
    print(f"[done] {done} cells in {time.time() - tgen:.0f}s; {vram('final')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
