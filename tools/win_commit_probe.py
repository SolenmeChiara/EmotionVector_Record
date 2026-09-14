#!/usr/bin/env python3
"""Find out what actually eats Windows commit charge when loading this model.

Error 1455 (ERROR_COMMITMENT_LIMIT, "the paging file is too small") killed the
first real load attempt. Two suspects:
  A. the 16 GB single-file safetensors memory map
  B. the CUDA/WDDM backing store, which reserves system commit roughly 1:1 with
     VRAM allocations so the OS can evict them
This measures each in isolation and prints the commit charge before/after.
"""
from __future__ import annotations

import ctypes
import os
import sys


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def commit() -> tuple[float, float]:
    """(commit charge GB, commit limit GB) - ullTotalPageFile is the limit."""
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    limit = st.ullTotalPageFile / 2**30
    avail = st.ullAvailPageFile / 2**30
    return limit - avail, limit


def show(tag: str) -> None:
    c, lim = commit()
    print(f"  [{tag:24s}] commit={c:6.2f}G / limit={lim:6.2f}G  avail={lim - c:6.2f}G", flush=True)


# Snapshot directory to memory-map. Resolved inside whatever HF cache is configured
# (HF_HOME, else a `hf-cache` dir next to the repo); override wholesale with
# EMOPROBE_SNAPSHOT if your checkpoint lives somewhere else.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HF_CACHE = os.environ.get("HF_HOME") or os.path.join(_REPO_ROOT, "hf-cache")
SNAP = os.environ.get(
    "EMOPROBE_SNAPSHOT",
    os.path.join(
        _HF_CACHE,
        "hub",
        "models--google--gemma-4-E4B-it",
        "snapshots",
        "ee0ef6023621cff504d758262d4e04895a5af4a2",
    ),
)


def probe_mmap() -> None:
    print("A. safetensors memory map of the 16 GB single-file checkpoint")
    from safetensors import safe_open

    show("before open")
    f = safe_open(os.path.join(SNAP, "model.safetensors"), framework="pt", device="cpu")
    keys = list(f.keys())
    show(f"after open ({len(keys)} keys)")
    t = f.get_tensor(keys[0])
    print(f"     first tensor {keys[0]}: {tuple(t.shape)} {t.dtype}")
    show("after 1 tensor read")
    # touch a big one to force pages in
    big = max(keys, key=lambda k: 1)  # placeholder; read a known-large table below
    del big
    del f, t
    show("after close")


def probe_gpu(gb: float) -> None:
    print(f"\nB. CUDA allocation of {gb:.0f} GB on the GPU")
    import torch

    show("before cuda init")
    torch.cuda.init()
    show("after cuda init")
    n = int(gb * 2**30 // 2)  # fp16 elements
    x = torch.empty(n, dtype=torch.float16, device="cuda")
    torch.cuda.synchronize()
    show(f"after {gb:.0f}G cuda alloc")
    free, total = torch.cuda.mem_get_info()
    print(f"     vram free={free / 2**30:.2f}G / {total / 2**30:.2f}G")
    del x
    torch.cuda.empty_cache()
    show("after free")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    show("process start")
    if which in ("mmap", "both"):
        probe_mmap()
    if which in ("gpu", "both"):
        probe_gpu(float(sys.argv[2]) if len(sys.argv) > 2 else 10.0)
