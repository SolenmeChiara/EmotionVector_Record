# Dependencies

## External repository (not vendored)

This project was developed alongside **persona_vectors**, which is *not* included in this
repository. It is a separate Apache-2.0 project with its own history and license; clone it
yourself rather than expecting a copy here:

    https://github.com/safety-research/persona_vectors

    git clone https://github.com/safety-research/persona_vectors.git

Nothing in `core/` or `tools/` imports it at runtime — it was read as a methodological
reference (direction extraction and activation steering) while this code was being written.
Clone it next to this repo if you want to compare implementations.

## Python packages

There is no pinned `requirements.txt` in the original project. The versions below are the
ones actually installed in the environment that produced every number in the reports, read
off the run environment's package metadata. Treat them as "known good", not as minimums.

| Package | Version |
|---|---|
| torch | 2.11.0+cu128 |
| transformers | 5.17.0 |
| accelerate | 1.15.0 |
| bitsandbytes | 0.50.2 |
| safetensors | 0.8.0 |
| numpy | 2.5.3 |
| scikit-learn | 1.9.1 |
| scipy | 1.18.1 |
| matplotlib | 3.11.2 |
| pillow | 12.3.0 |
| huggingface_hub | 1.31.0 |

`bitsandbytes` is only needed for the 8-bit Gemma path; `pillow` only for the card renderer
in `tools/render_heatmaps.py`. Everything else in the codebase is standard library.

Corpus generation (`core/gen_stories.py`) additionally needs a local
[Ollama](https://ollama.com) server; it talks to `OLLAMA_HOST`, defaulting to Ollama's own
`http://127.0.0.1:11434`.

## Environment variables

| Variable | Purpose |
|---|---|
| `HF_HOME` | Where model weights are cached. Defaults to `hf-cache/` next to the repo. |
| `HF_HUB_DISABLE_XET` | Set to `1`. The Xet transfer backend was unusable on the development machine; see `WINDOWS_RUN.md`. |
| `OLLAMA_HOST` | Corpus generation only. Defaults to `http://127.0.0.1:11434`. |
| `EMOPROBE_KEEP_WARMUP` | Set to re-enable `transformers`' `caching_allocator_warmup`, which `core/common.py` disables on Windows. See the docstring there for why. |
| `EMOPROBE_SNAPSHOT` | `tools/win_commit_probe.py` only — overrides which model snapshot directory it memory-maps. |
