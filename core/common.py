#!/usr/bin/env python3
"""Shared model loading / path helpers for the emotion probe."""
from __future__ import annotations

import json
import os

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")

# Hugging Face cache location. Set HF_HOME to point at wherever the weights live
# (a large data drive is a good idea - the Gemma checkpoint alone is ~16 GB); the
# fallback keeps the cache next to the repo so a fresh clone runs unconfigured.
# If you run the same weights from both Windows and WSL, point HF_HOME at the same
# physical directory from each side so nothing is downloaded twice.
HF_CACHE = os.environ.get("HF_HOME") or os.path.join(ROOT, "hf-cache")
os.environ.setdefault("HF_HOME", HF_CACHE)
os.environ.setdefault("HF_HUB_CACHE", os.path.join(HF_CACHE, "hub"))

DEFAULT_MODEL = "Qwen/Qwen3.5-4B"
GROUPS = ["happy", "sad", "angry", "fearful", "neutral"]
EMOTIONS = ["happy", "sad", "angry", "fearful"]

# Phase three. The sensation corpus reuses the SAME neutral control as the
# emotion corpus rather than generating its own, so both direction sets are
# centred against a grand mean containing the identical 40 control passages.
# Without that, `cos(d_warm, d_happy)` would also be measuring the difference
# between two independently sampled controls.
SENSATIONS = ["warm", "cold", "pain"]
SENS_GROUPS = ["warm", "cold", "pain", "neutral"]


def disable_cuda_warmup() -> bool:
    """Stop transformers from pre-reserving most of the GPU before loading.

    `caching_allocator_warmup` fires one big `torch.empty` of up to
    `total_device_memory - 1.2 GiB` so the caching allocator does not have to
    grow during loading. It is purely a speed optimisation, and on Linux it is
    free. On Windows it is not: WDDM reserves a host backing store for every GPU
    allocation, so that single call also charges ~14.7 GiB of system commit.
    Measured on this box (tools/win_commit_probe.py): a 10 GiB CUDA allocation
    raises the commit charge by 10.3 GiB. With a 62.5 GiB commit limit that is
    already ~40 GiB full at idle, the warmup alone pushed the loader over the
    edge and the load died with OSError 1455 / got killed by the watchdog.

    Turning it off costs load time and nothing else.
    """
    if os.environ.get("EMOPROBE_KEEP_WARMUP"):
        return False
    try:
        import transformers.modeling_utils as mu
    except Exception:  # noqa: BLE001
        return False
    if not hasattr(mu, "caching_allocator_warmup"):
        return False
    mu.caching_allocator_warmup = lambda *a, **k: None
    return True


def vram(tag: str = "") -> str:
    if not torch.cuda.is_available():
        return f"[vram {tag}] cuda unavailable"
    a = torch.cuda.memory_allocated() / 2**30
    r = torch.cuda.memory_reserved() / 2**30
    p = torch.cuda.max_memory_allocated() / 2**30
    free, total = torch.cuda.mem_get_info()
    return (
        f"[vram {tag}] alloc={a:.2f}G reserved={r:.2f}G peak_alloc={p:.2f}G "
        f"device_free={free / 2**30:.2f}G/{total / 2**30:.2f}G"
    )


def load_model(
    model_id: str = DEFAULT_MODEL,
    dtype=torch.bfloat16,
    load_in_8bit: bool = False,
    offload: list[str] | None = None,
    max_memory_gpu: str | None = None,
):
    """Load tokenizer + causal LM, returning (model, tok, text_model, n_layers).

    Qwen3.5 ships as a vision-language ForConditionalGeneration checkpoint, so
    the decoder stack we want lives one level down. `text_model` is the module
    whose `.layers` list we hook for steering; `n_layers` counts decoder blocks.

    `offload` is a list of module-name prefixes to pin to CPU while everything
    else goes to the GPU. Gemma-4 E-series needs this: its per-layer embedding
    table (`embed_tokens_per_layer`, vocab x n_layers x 256) is several GB of
    pure lookup that never needs to sit in VRAM, and the vision/audio towers are
    dead weight for a text-only probe.
    `max_memory_gpu` (e.g. "12GiB") switches to accelerate's automatic split
    instead, as a fallback when the explicit map does not fit.
    """
    import transformers
    from transformers import AutoTokenizer

    if os.name == "nt" and disable_cuda_warmup():
        print("[load] windows: caching_allocator_warmup disabled (WDDM commit charge)")

    if load_in_8bit:
        # bitsandbytes logs "MatMul8bitLt: inputs will be cast from bfloat16 to
        # float16" on *every* int8 matmul - roughly 40k lines per 150-token
        # sample, which turned a steering log into megabytes in seconds. The
        # fact itself matters (the 8bit path computes in fp16) but it only needs
        # saying once.
        import logging

        logging.getLogger("bitsandbytes").setLevel(logging.ERROR)
        print("[load] 8bit: int8 matmuls compute in fp16 (bnb per-call warning silenced)")

    try:
        tok = AutoTokenizer.from_pretrained(model_id)
    except Exception as e:  # noqa: BLE001 - some VL repos only ship a processor
        print(f"[load] AutoTokenizer failed ({e}); falling back to AutoProcessor")
        from transformers import AutoProcessor

        tok = AutoProcessor.from_pretrained(model_id).tokenizer

    on_gpu = torch.cuda.is_available()
    if offload:
        device_map: str | dict = build_device_map(model_id, offload, 0 if on_gpu else "cpu")
        n_cpu = sum(1 for v in device_map.values() if v == "cpu")
        print(f"[load] explicit device_map: {len(device_map)} entries, {n_cpu} pinned to cpu")
    elif max_memory_gpu:
        device_map = "auto"
    else:
        device_map = "cuda:0" if on_gpu else "cpu"

    kwargs: dict = {"device_map": device_map}
    if offload or max_memory_gpu:
        # Without this, accelerate can leave an offloaded module's buffers on the
        # meta device and the first forward dies with "Cannot copy out of meta
        # tensor" (hit on Gemma-4 E4B's per-layer embedding table).
        kwargs["offload_buffers"] = True
    if max_memory_gpu:
        kwargs["max_memory"] = {0: max_memory_gpu, "cpu": "10GiB"}
    if load_in_8bit:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    else:
        kwargs["dtype"] = dtype

    # Qwen3.5 / Gemma4 checkpoints are *ForConditionalGeneration classes, which
    # AutoModelForCausalLM may refuse. Walk the auto-class candidates in order
    # and report which one actually took the checkpoint.
    candidates = ["AutoModelForCausalLM", "AutoModelForImageTextToText", "AutoModel"]
    model = None
    errors = []
    for name in candidates:
        cls = getattr(transformers, name, None)
        if cls is None:
            continue
        try:
            model = cls.from_pretrained(model_id, **kwargs)
            print(f"[load] loaded via {name}")
            break
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {type(e).__name__}: {e}")
    if model is None:
        raise RuntimeError("no auto class accepted the checkpoint:\n  " + "\n  ".join(errors))
    model.eval()

    text_model = find_text_model(model)
    n_layers = len(text_model.layers)
    return model, tok, text_model, n_layers


def build_device_map(model_id: str, offload: list[str], main_device) -> dict:
    """Build a COMPLETE module -> device map pinning `offload` prefixes to CPU.

    A partial dict plus a `{"": main}` catch-all does NOT work: transformers
    collapses it and everything lands on the main device (verified on this box -
    the offloaded modules stayed on the GPU and VRAM was unchanged). So the map
    has to name every top-level module explicitly, expanding only along the
    paths that actually contain an offload target.

    The skeleton is instantiated on the meta device, so this costs no memory and
    no disk read beyond the config.
    """
    from accelerate import init_empty_weights
    from transformers import AutoConfig, AutoModelForCausalLM

    cfg = AutoConfig.from_pretrained(model_id)
    with init_empty_weights():
        skeleton = AutoModelForCausalLM.from_config(cfg)

    # Resolve the requested prefixes against the module names the loader will
    # actually produce. The auto class often builds a text-only model, so the
    # checkpoint's `model.language_model.embed_tokens_per_layer` shows up as
    # `model.embed_tokens_per_layer`; a bare suffix therefore also matches.
    all_paths = [n for n, _ in skeleton.named_modules() if n]
    targets = {
        path
        for path in all_paths
        for p in offload
        if path == p or path.startswith(p + ".") or path.endswith("." + p)
    }
    # Drop targets nested inside another target - the outer one already covers them.
    targets = {t for t in targets if not any(t.startswith(o + ".") for o in targets if o != t)}

    out: dict = {}

    def walk(module, path: str) -> None:
        if path in targets:
            out[path] = "cpu"
            return
        children = list(module.named_children())
        below = any(t.startswith(path + ".") for t in targets)
        if not below or not children:
            out[path] = main_device
            return
        for name, child in children:
            walk(child, f"{path}.{name}")
        if any(True for _ in module.named_parameters(recurse=False)):
            out[path] = main_device

    for name, child in skeleton.named_children():
        walk(child, name)

    stray = [n for n, _ in skeleton.named_parameters(recurse=False)]
    if stray:
        print(f"[device_map] warning: root-level parameters not covered: {stray}")
    if not targets:
        print(f"[device_map] warning: offload prefixes matched nothing: {offload}")
    else:
        print(f"[device_map] offloading to cpu: {sorted(targets)}")
    del skeleton
    return out


def find_text_model(model):
    """Locate the module that owns the decoder `.layers` ModuleList."""
    candidates = [
        "model.language_model",
        "model.text_model",
        "language_model.model",
        "model",
        "transformer",
    ]
    for path in candidates:
        cur = model
        ok = True
        for part in path.split("."):
            if hasattr(cur, part):
                cur = getattr(cur, part)
            else:
                ok = False
                break
        if ok and hasattr(cur, "layers"):
            return cur
    # last resort: breadth-first hunt for any submodule with `.layers`
    for name, mod in model.named_modules():
        if hasattr(mod, "layers") and isinstance(
            mod.layers, torch.nn.ModuleList
        ):
            print(f"[find_text_model] fell back to '{name}'")
            return mod
    raise RuntimeError("could not locate decoder layer list")


def load_stories(groups=None) -> list[dict]:
    groups = groups or GROUPS
    rows: list[dict] = []
    for g in groups:
        path = os.path.join(DATA, f"stories_{g}.jsonl")
        with open(path, encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
    return rows
