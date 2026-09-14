#!/usr/bin/env python3
"""Phase four step 1 - per-token projections onto the seven directions, plus logit lens.

One forward pass per passage (no generation, no hooks). At hidden_states[17] every
token position gives a residual vector h_t; each of the seven directions turns that
into a scalar per token. The whole point of the figure is that those scalars are
readable as highlight intensity over the text.

Four ways of making the scalar are computed and stored side by side, because the
naive one is misleading:

  raw             (h_t - grand_mean) . d
                  grand_mean is that corpus's training grand mean, i.e. exactly the
                  centre the direction was fitted around. Still dominated by the
                  shared "this text is in SOME marked state" component that
                  BUILD_REPORT_3 sec 3.1 measured at cos = +0.864 between the two
                  corpora's generic axes. Expect near-everything positive.
  center          (h_t - mean_t h_t) . d
                  centred on this passage's own token mean. Anything constant across
                  the passage - genre, register, the shared floor, the layer's own
                  mean offset - drops out, leaving only which tokens stand out
                  *within* this text. Cheap, model-free, needs no corpus.
  partial         (h_t - grand_mean) . d_perp,  d_perp = unit(d - a (a.d))
                  the BUILD_REPORT_3 treatment: project the corpus's generic axis a
                  out of the direction first. Keeps absolute level comparable across
                  passages (unlike center), but only removes the one axis we named.
  center_partial  both at once.

Also, once the model is in memory, the logit lens: W_U (times the final norm's
learned gain, which is the linearisation of RMSNorm and only costs a positive
scalar in the ranking) applied to each direction, top-k up and down.

Writes one JSON per passage into results/tokenmaps/ as it goes - a dropped run
keeps everything already computed.
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

EMO_GROUPS = ["happy", "sad", "angry", "fearful", "neutral"]
SENS_GROUPS = ["warm", "cold", "pain", "neutral"]
MODES = ["raw", "center", "partial", "center_partial"]


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def load_directions(layer: int, which: str):
    """Seven unit directions at `layer`, each with its corpus's grand mean and generic axis.

    The two corpora were fitted separately (four emotions + neutral; three
    sensations + the SAME neutral control), so each carries its own centre. Mixing
    them up would silently shift every projection by the difference between two
    grand means.
    """
    ze = np.load(os.path.join(DATA, "directions.npz"), allow_pickle=True)
    zs = np.load(os.path.join(DATA, "directions_sens.npz"), allow_pickle=True)
    emos = [str(x) for x in ze["emotions"]]
    sens = [str(x) for x in zs["emotions"]]

    # Phase one's directions.npz predates the generic_axis key, so recompute it from
    # the activations with the identical split. Phase three's file stores one; it is
    # recomputed too and checked against the stored copy.
    ga_e = generic_axis(os.path.join(DATA, "acts.npz"), EMO_GROUPS, ["happy", "sad", "angry", "fearful"], 8, 7)
    ga_s = generic_axis(os.path.join(DATA, "acts_sens.npz"), SENS_GROUPS, ["warm", "cold", "pain"], 8, 7)
    if "generic_axis" in zs.files:
        agree = float(ga_s[layer] @ unit(zs["generic_axis"][layer]))
        print(f"[dirs] recomputed sensation generic axis vs stored: cos={agree:+.6f}")

    out = []
    for src, names, z, ga in (("emotion", emos, ze, ga_e), ("sensation", sens, zs, ga_s)):
        for i, name in enumerate(names):
            out.append({
                "name": name,
                "corpus": src,
                "d": unit(z[which][layer, i].astype(np.float64)),
                "grand": z["grand_means"][layer].astype(np.float64),
                "axis": unit(ga[layer].astype(np.float64)),
            })
    for r in out:
        a, d = r["axis"], r["d"]
        r["d_perp"] = unit(d - a * float(d @ a))
        r["axis_load"] = float(d @ a)
    print("[dirs] cos(direction, its corpus generic axis): "
          + ", ".join(f"{r['name']}={r['axis_load']:+.3f}" for r in out))
    return out


def token_display(text: str, offsets, ids, tok) -> list[str]:
    """Exact source substring per token where the fast tokenizer gives offsets.

    Falls back to a single-id decode for specials and for any token whose span is
    empty. Using offsets rather than per-id decoding keeps multi-byte characters
    from turning into replacement glyphs when a BPE piece splits one in half.
    """
    disp = []
    for (a, b), i in zip(offsets, ids):
        s = text[a:b] if b > a else ""
        if not s:
            s = tok.decode([int(i)], skip_special_tokens=False)
        disp.append(s)
    return disp


def logit_lens(model, tok, dirs, topk: int, out_path: str) -> None:
    emb = model.get_output_embeddings()
    if emb is None:
        print("[lens] no output embedding module; skipping")
        return
    W = emb.weight  # [vocab, hidden]
    # RMSNorm before the unembed is nonlinear in the vector's own scale, but its
    # learned per-channel gain is a plain diagonal matrix. Folding that in is the
    # correct linearisation; the dropped part is a positive scalar and cannot move
    # a ranking. Both variants are stored so the difference is inspectable.
    gain = None
    for path in ("model.language_model.norm", "model.norm", "norm"):
        cur = model
        ok = True
        for part in path.split("."):
            if not hasattr(cur, part):
                ok = False
                break
            cur = getattr(cur, part)
        if ok and hasattr(cur, "weight"):
            gain = cur.weight.detach().float()
            print(f"[lens] final norm gain from `{path}`, shape {tuple(gain.shape)}")
            break
    if gain is None:
        print("[lens] no final norm found; plain W_U only")

    special = {int(i) for i in (tok.all_special_ids or [])}
    try:
        special |= {int(i) for i in tok.get_added_vocab().values()}
    except Exception as e:  # noqa: BLE001 - slow tokenizers do not expose it
        print(f"[lens] get_added_vocab unavailable ({type(e).__name__}); special ids only")
    print(f"[lens] {len(special)} special/added ids excluded from the top lists")

    Wf = W.detach().float()
    g = gain if gain is not None else torch.ones(Wf.shape[1], device=Wf.device)
    # Two unembed matrices. The second has the mean token row subtracted: without
    # that, every direction's top list is partly just "which rows of W_U are long
    # and point the generic way", which is how unrelated directions end up sharing
    # the same handful of odd tokens. Centring is the standard fix and it costs one
    # subtraction.
    UNEMB = [("normgain", Wf), ("normgain_centered", Wf - Wf.mean(0, keepdim=True))]

    def is_ascii_id(i: int) -> bool:
        s = tok.decode([i], skip_special_tokens=False)
        return bool(s.strip()) and s.isascii()

    blob = {"layer_note": "direction vectors at hidden_states[17]", "topk": topk,
            "n_excluded_special": len(special),
            "unembed_variants": [u[0] for u in UNEMB],
            "directions": {}}

    def take(scores, order, want, ascii_only):
        out = []
        for i in order:
            if len(out) >= want:
                break
            i = int(i)
            if i in special:
                continue
            if ascii_only and not is_ascii_id(i):
                continue
            out.append(tok_entry(tok, i, float(scores[i])))
        return out

    for r in dirs:
        entry = {}
        for tag, vec in (("raw", r["d"]), ("partial", r["d_perp"])):
            v = torch.tensor(vec, dtype=torch.float32, device=Wf.device) * g
            for utag, M in UNEMB:
                scores = (M @ v).cpu().numpy()
                order = np.argsort(scores)
                entry[f"{tag}_{utag}"] = {
                    "up": take(scores, order[::-1], topk, False),
                    "down": take(scores, order, topk, False),
                    "up_ascii": take(scores, order[::-1], topk, True),
                    "down_ascii": take(scores, order, topk, True),
                    "score_std": float(scores.std()),
                }
            # How much of the ranking was the final norm's gain doing? One number,
            # so the choice to fold it in is auditable without a second full table.
            if gain is not None:
                v0 = torch.tensor(vec, dtype=torch.float32, device=Wf.device)
                s0 = (Wf @ v0).cpu().numpy()
                a = {x["id"] for x in entry[f"{tag}_normgain"]["up"]}
                b = {int(i) for i in np.argsort(s0)[::-1][: topk * 2] if int(i) not in special}
                entry[f"{tag}_gain_overlap_top{topk}"] = len(a & b)
        blob["directions"][r["name"]] = entry
        print(f"  lens {r['name']:8s} partial/centered up: "
              + " ".join(x["show"] for x in entry["partial_normgain_centered"]["up"][:10]))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(blob, f, indent=2, ensure_ascii=False)
    print(f"-> {out_path}")


def tok_entry(tok, i: int, score: float) -> dict:
    piece = tok.convert_ids_to_tokens(i)
    s = tok.decode([i], skip_special_tokens=False)
    show = s.replace(" ", "␣") if s else (piece or f"<{i}>")
    return {"id": i, "piece": piece, "text": s, "show": show, "score": round(score, 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3.5-4B")
    ap.add_argument("--layer", type=int, default=17)
    ap.add_argument("--which", default="dirs_raw", choices=["dirs_raw", "dirs_denoised"])
    ap.add_argument("--texts", default=os.path.join(DATA, "heatmap_texts.json"))
    ap.add_argument("--outdir", default=os.path.join(RESULTS, "tokenmaps"))
    ap.add_argument("--lens-out", default=os.path.join(RESULTS, "logit_lens_qwen.json"))
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--skip-lens", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    with open(args.texts, encoding="utf-8") as f:
        passages = json.load(f)["passages"]
    dirs = load_directions(args.layer, args.which)
    names = [r["name"] for r in dirs]

    print(f"[env] torch {torch.__version__} cuda={torch.cuda.is_available()}")
    print(vram("pre-load"))
    t0 = time.time()
    model, tok, _tm, n_layers = load_model(args.model)
    print(f"[load] {args.model}: {n_layers} decoder blocks in {time.time() - t0:.1f}s; {vram('post-load')}")

    D = np.stack([r["d"] for r in dirs])          # [7, H]
    Dp = np.stack([r["d_perp"] for r in dirs])    # [7, H]
    G = np.stack([r["grand"] for r in dirs])      # [7, H]

    t0 = time.time()
    with torch.inference_mode():
        for pi, p in enumerate(passages):
            enc = tok(p["text"], return_tensors="pt", add_special_tokens=True,
                      return_offsets_mapping=True)
            offsets = enc.pop("offset_mapping")[0].tolist()
            ids = enc["input_ids"][0].tolist()
            enc = {k: v.to(model.device) for k, v in enc.items()}
            out = model(**enc, output_hidden_states=True, use_cache=False)
            H = out.hidden_states[args.layer][0].float().cpu().numpy().astype(np.float64)  # [T, hid]
            del out

            mean_t = H.mean(0, keepdims=True)
            proj = {}
            proj["raw"] = np.stack([(H - G[i]) @ D[i] for i in range(len(dirs))], axis=0)
            proj["center"] = (H - mean_t) @ D.T
            proj["center"] = proj["center"].T
            proj["partial"] = np.stack([(H - G[i]) @ Dp[i] for i in range(len(dirs))], axis=0)
            proj["center_partial"] = ((H - mean_t) @ Dp.T).T

            rec = {
                "id": p["id"], "family": p["family"], "title": p["title"], "note": p["note"],
                "expect": p["expect"], "words": p["words"], "text": p["text"],
                "layer": args.layer, "which": args.which, "model": args.model,
                "directions": names,
                "tokens": token_display(p["text"], offsets, ids, tok),
                "token_ids": ids,
                "token_norm": [round(float(x), 3) for x in np.linalg.norm(H, axis=1)],
                "n_tokens": len(ids),
                "proj": {m: [[round(float(x), 4) for x in row] for row in proj[m]] for m in MODES},
                "passage_mean": {m: {names[i]: round(float(proj[m][i].mean()), 4)
                                     for i in range(len(dirs))} for m in MODES},
            }
            path = os.path.join(args.outdir, f"{p['id']}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False)
            # Report the `partial` mean, not a centred one: centring makes the
            # passage mean identically zero by construction, so it says nothing.
            top = sorted(rec["passage_mean"]["partial"].items(), key=lambda kv: -kv[1])[:3]
            print(f"  [{pi + 1:2d}/{len(passages)}] {p['id']:26s} T={len(ids):4d} expect={p['expect']:8s} "
                  f"top(partial)=" + ", ".join(f"{k} {v:+.3f}" for k, v in top), flush=True)

    print(f"[done] {len(passages)} passages in {time.time() - t0:.1f}s; {vram('after fwd')}")

    if not args.skip_lens:
        logit_lens(model, tok, dirs, args.topk, args.lens_out)

    print(vram("final"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
