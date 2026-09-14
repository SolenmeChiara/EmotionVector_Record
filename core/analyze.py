#!/usr/bin/env python3
"""Steps 2-4 - directions, held-out readout, logistic-regression control, heatmap.

Method (RECON "方法配方" 2-4, difference-of-means as the main line):
  * hold out `--holdout` stories per group; they never touch direction fitting
  * per layer, per emotion:  d_g = mean(train acts of g) - mean(train acts of ALL groups)
    (grand mean includes the other emotions and the neutral control, so the
     generic "this is an emotional short story" component largely cancels)
  * optional denoise: project out the top 50% principal components of the
    neutral training set
  * readout: (x - grand_mean) . d_g_hat  ->  argmax over emotions
  * control: multinomial logistic regression on the same split
  * sanity floor: the same pipeline with training labels shuffled

Outputs results/heatmap.png, results/accuracy_by_layer.png,
results/metrics.json and data/directions.npz.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, EMOTIONS, GROUPS, RESULTS


def split_indices(labels: np.ndarray, holdout: int, seed: int, groups=GROUPS):
    rng = np.random.default_rng(seed)
    train, test = [], []
    for gi in range(len(groups)):
        idx = np.where(labels == gi)[0]
        rng.shuffle(idx)
        test.extend(idx[:holdout].tolist())
        train.extend(idx[holdout:].tolist())
    return np.array(sorted(train)), np.array(sorted(test))


def neutral_pc_basis(train_acts: np.ndarray, train_labels: np.ndarray, frac: float, groups=GROUPS):
    """Top `frac` principal components of the neutral training activations."""
    ni = np.where(train_labels == groups.index("neutral"))[0]
    X = train_acts[ni]
    X = X - X.mean(0, keepdims=True)
    # economical SVD: n_samples << hidden
    _, _, Vt = np.linalg.svd(X, full_matrices=False)
    k = max(1, round(Vt.shape[0] * frac))
    return Vt[:k]  # [k, hidden], orthonormal rows


def remove_subspace(d: np.ndarray, basis: np.ndarray) -> np.ndarray:
    return d - basis.T @ (basis @ d)


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def fit_layer(acts_l, labels, train, test, denoise_basis=None, groups=GROUPS, targets=EMOTIONS):
    """Return directions [n_targets, hidden], grand mean, and readout scores."""
    Xtr, ytr = acts_l[train], labels[train]
    grand = Xtr.mean(0)
    dirs = []
    for g in targets:
        gi = groups.index(g)
        d = Xtr[ytr == gi].mean(0) - grand
        if denoise_basis is not None:
            d = remove_subspace(d, denoise_basis)
        dirs.append(unit(d))
    D = np.stack(dirs)  # [4, hidden]
    proj_test = (acts_l[test] - grand) @ D.T  # [n_test, 4]
    proj_train = (Xtr - grand) @ D.T
    return D, grand, proj_test, proj_train


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt((va + vb) / 2)
    if pooled == 0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def emotion_accuracy(proj: np.ndarray, y: np.ndarray, groups=GROUPS, targets=EMOTIONS) -> float:
    """N-way accuracy restricted to the non-control stories in this split."""
    emo_ids = [groups.index(e) for e in targets]
    mask = np.isin(y, emo_ids)
    if mask.sum() == 0:
        return float("nan")
    pred = proj[mask].argmax(1)
    true = np.array([emo_ids.index(v) for v in y[mask]])
    return float((pred == true).mean())


def five_way_accuracy(proj: np.ndarray, y: np.ndarray, groups=GROUPS, targets=EMOTIONS) -> float:
    """Include the control: neutral is predicted when every projection is <= 0."""
    pred_emo = proj.argmax(1)
    best = proj.max(1)
    neutral_i = groups.index("neutral")
    pred = np.where(best <= 0, neutral_i, [groups.index(targets[i]) for i in pred_emo])
    return float((pred == y).mean())


def logreg_accuracy(acts_l, labels, train, test, seed, groups=GROUPS, targets=EMOTIONS):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    emo_ids = [groups.index(e) for e in targets]
    tr = train[np.isin(labels[train], emo_ids)]
    te = test[np.isin(labels[test], emo_ids)]
    sc = StandardScaler().fit(acts_l[tr])
    clf = LogisticRegression(max_iter=3000, C=0.1, random_state=seed)
    clf.fit(sc.transform(acts_l[tr]), labels[tr])
    acc4 = float(clf.score(sc.transform(acts_l[te]), labels[te]))
    sc5 = StandardScaler().fit(acts_l[train])
    clf5 = LogisticRegression(max_iter=3000, C=0.1, random_state=seed)
    clf5.fit(sc5.transform(acts_l[train]), labels[train])
    acc5 = float(clf5.score(sc5.transform(acts_l[test]), labels[test]))
    return acc4, acc5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--acts", default=os.path.join(DATA, "acts.npz"))
    ap.add_argument("--holdout", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--pc-frac", type=float, default=0.5)
    ap.add_argument("--tag", default="")
    ap.add_argument("--groups", default="", help="story groups in label order (default: emotions + neutral)")
    ap.add_argument("--targets", default="", help="the groups to fit directions for (default: the four emotions)")
    args = ap.parse_args()

    groups = [g for g in args.groups.split(",") if g] or GROUPS
    targets = [g for g in args.targets.split(",") if g] or EMOTIONS
    if "neutral" not in groups:
        raise SystemExit("--groups must contain 'neutral': it is the control the grand mean and the denoising basis are built from")
    missing = [t for t in targets if t not in groups]
    if missing:
        raise SystemExit(f"--targets not present in --groups: {missing}")

    # Label figures with the model the activations actually came from, read
    # from the sidecar metadata extract.py writes next to the .npz.
    meta_path = os.path.splitext(args.acts)[0] + "_meta.json"
    model_label = "unknown model"
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            mm = json.load(f)
        model_label = mm.get("model", model_label)
        if mm.get("eightbit"):
            model_label += " (8bit)"

    z = np.load(args.acts, allow_pickle=True)
    acts, labels = z["acts"], z["labels"]
    norms = z["norms"]
    L = acts.shape[0]
    print(f"[data] acts {acts.shape} (hidden_states index 0 = embeddings)")

    # The label column indexes into whatever group list extract.py was run with.
    # Trust the npz over the CLI when the file records it, so a mismatched
    # --groups cannot silently relabel the data.
    if "groups" in z.files:
        stored = [str(x) for x in z["groups"]]
        if stored != groups:
            raise SystemExit(f"--groups {groups} does not match the order stored in {args.acts}: {stored}")
    print(f"[groups] {groups}; fitting directions for {targets}")

    train, test = split_indices(labels, args.holdout, args.seed, groups)
    print(f"[split] train {len(train)} / holdout {len(test)}")

    # Sanity floor: permute the TRAINING labels only, leave held-out labels
    # intact, then run the identical pipeline. Whatever accuracy that reaches is
    # what this split can produce from nothing.
    rng = np.random.default_rng(args.seed + 1)
    shuf_train_labels = labels.copy()
    shuf_train_labels[train] = rng.permutation(labels[train])

    per_layer = []
    dirs_raw = np.zeros((L, len(targets), acts.shape[2]), dtype=np.float32)
    dirs_dn = np.zeros_like(dirs_raw)
    grands = np.zeros((L, acts.shape[2]), dtype=np.float32)
    # The "is this passage in ANY target state at all" axis, per layer: the mean
    # of the target groups minus the grand mean. Phase three needs it because a
    # cosine between a sensation direction and an emotion direction is partly
    # this shared non-neutral component rather than anything specific.
    generic = np.zeros((L, acts.shape[2]), dtype=np.float32)

    for l in range(L):
        A = acts[l]
        basis = neutral_pc_basis(A[train], labels[train], args.pc_frac, groups)
        D, grand, pt, _ = fit_layer(A, labels, train, test, groups=groups, targets=targets)
        Dd, _, ptd, _ = fit_layer(
            A, labels, train, test, denoise_basis=basis, groups=groups, targets=targets
        )
        dirs_raw[l], dirs_dn[l], grands[l] = D, Dd, grand
        tgt_ids = [groups.index(t) for t in targets]
        g_vec = A[train][np.isin(labels[train], tgt_ids)].mean(0) - grand
        generic[l] = unit(g_vec)

        # per-target held-out separation (Cohen's d, in-group vs rest)
        ds, ds_dn = [], []
        for ei, e in enumerate(targets):
            gi = groups.index(e)
            m = labels[test] == gi
            ds.append(cohens_d(pt[m, ei], pt[~m, ei]))
            ds_dn.append(cohens_d(ptd[m, ei], ptd[~m, ei]))

        _, _, pts, _ = fit_layer(A, shuf_train_labels, train, test, groups=groups, targets=targets)
        acc4_lr, acc5_lr = logreg_accuracy(A, labels, train, test, args.seed, groups, targets)

        row = {
            "layer": l,
            "mean_norm": float(norms[l]),
            "acc4_diffmean": emotion_accuracy(pt, labels[test], groups, targets),
            "acc4_diffmean_denoised": emotion_accuracy(ptd, labels[test], groups, targets),
            "acc5_diffmean": five_way_accuracy(pt, labels[test], groups, targets),
            "acc4_logreg": acc4_lr,
            "acc5_logreg": acc5_lr,
            "acc4_shuffled_control": emotion_accuracy(pts, labels[test], groups, targets),
            "cohens_d": {e: round(v, 3) for e, v in zip(targets, ds)},
            "cohens_d_denoised": {e: round(v, 3) for e, v in zip(targets, ds_dn)},
            "cohens_d_mean": float(np.mean(ds)),
            "cohens_d_mean_denoised": float(np.mean(ds_dn)),
        }
        per_layer.append(row)
        print(
            f"  L{l:02d} norm={norms[l]:7.2f} d̄={row['cohens_d_mean']:.2f} "
            f"acc4 dm={row['acc4_diffmean']:.2f} dn={row['acc4_diffmean_denoised']:.2f} "
            f"lr={acc4_lr:.2f} shuf={row['acc4_shuffled_control']:.2f}"
        )

    d_mat = np.array([[r["cohens_d"][e] for e in targets] for r in per_layer])
    d_mat_dn = np.array([[r["cohens_d_denoised"][e] for e in targets] for r in per_layer])
    acc4 = np.array([r["acc4_diffmean"] for r in per_layer])
    acc4dn = np.array([r["acc4_diffmean_denoised"] for r in per_layer])
    acc4lr = np.array([r["acc4_logreg"] for r in per_layer])
    acc4sh = np.array([r["acc4_shuffled_control"] for r in per_layer])
    dbar = d_mat.mean(1)

    rank = np.argsort(-dbar)
    best_layers = [int(x) for x in rank[:5]]

    # Steering-layer pick. Two corrections to a naive argmax of Cohen's d:
    #  * index 0 is the embedding output and the LAST index is taken after the
    #    final RMSNorm (its residual norm jumps by ~3x), so neither is a decoder
    #    block output we can meaningfully inject into. Both are excluded.
    #  * rank by a combined score of separation and held-out accuracy, then keep
    #    picks at least `spread` indices apart so the two choices are not
    #    adjacent layers carrying the same information.
    lo, hi = 1, L - 1
    combo = np.full(L, -np.inf)
    sl = slice(lo, hi)
    combo[sl] = dbar[sl] / max(dbar[sl].max(), 1e-9) + acc4[sl] / max(acc4[sl].max(), 1e-9)
    spread = 4
    steer_layers: list[int] = []
    for cand in np.argsort(-combo):
        cand = int(cand)
        if combo[cand] == -np.inf:
            break
        if all(abs(cand - s) >= spread for s in steer_layers):
            steer_layers.append(cand)
        if len(steer_layers) == 2:
            break
    print(f"[steering layers] {steer_layers} (combined separation+accuracy score, "
          f"embeddings and post-final-norm index excluded)")
    print(f"\n[best by mean Cohen's d] {[(int(l), round(float(dbar[l]), 3)) for l in rank[:5]]}")
    print(f"[best by acc4 diff-mean]  {[(int(l), round(float(acc4[l]), 3)) for l in np.argsort(-acc4)[:5]]}")

    os.makedirs(RESULTS, exist_ok=True)
    plot(d_mat, d_mat_dn, acc4, acc4dn, acc4lr, acc4sh, args.tag, model_label, targets)

    metrics = {
        "acts_file": args.acts,
        "groups": groups,
        "targets": targets,
        "chance_nway": round(1.0 / len(targets), 3),
        "holdout_per_group": args.holdout,
        "seed": args.seed,
        "pc_frac": args.pc_frac,
        "n_train": len(train),
        "n_holdout": len(test),
        "chance_4way": 0.25,
        "chance_5way": 0.2,
        "best_layers_by_cohens_d": best_layers,
        "best_layers_by_acc4": [int(x) for x in np.argsort(-acc4)[:5]],
        "steering_layers": steer_layers,
        "steering_layer_note": (
            "hidden_states index k is the output of decoder block k-1; index 0 "
            "(embeddings) and the final index (post-final-RMSNorm) are excluded "
            "from the steering pick"
        ),
        "best_layer_scores": {
            str(int(l)): {
                "cohens_d_mean": round(float(dbar[l]), 3),
                "acc4_diffmean": round(float(acc4[l]), 3),
                "acc4_logreg": round(float(acc4lr[l]), 3),
            }
            for l in rank[:5]
        },
        "peak_acc4_diffmean": {
            "layer": int(acc4.argmax()),
            "value": round(float(acc4.max()), 3),
        },
        "peak_acc4_denoised": {
            "layer": int(acc4dn.argmax()),
            "value": round(float(acc4dn.max()), 3),
        },
        "peak_acc4_logreg": {
            "layer": int(acc4lr.argmax()),
            "value": round(float(acc4lr.max()), 3),
        },
        "shuffled_control_mean": round(float(acc4sh.mean()), 3),
        "shuffled_control_max": round(float(acc4sh.max()), 3),
        "per_layer": per_layer,
    }
    with open(os.path.join(RESULTS, f"metrics{args.tag}.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    np.savez_compressed(
        os.path.join(DATA, f"directions{args.tag}.npz"),
        dirs_raw=dirs_raw,
        dirs_denoised=dirs_dn,
        grand_means=grands,
        norms=norms,
        # kept under the phase-one key so directions.npz / directions_9b.npz /
        # directions_gemma4.npz stay readable by every existing consumer
        emotions=np.array(targets),
        generic_axis=generic,
        cohens_d=d_mat,
        acc4=acc4,
    )
    print(f"-> {RESULTS}/metrics{args.tag}.json, {DATA}/directions{args.tag}.npz")
    return 0


def plot(d_mat, d_mat_dn, acc4, acc4dn, acc4lr, acc4sh, tag, label, targets=EMOTIONS):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    L = d_mat.shape[0]
    fig, axes = plt.subplots(
        2, 1, figsize=(max(12, L * 0.46), 8.0), gridspec_kw={"height_ratios": [1, 1]}
    )
    # Cohen's d here is in-group minus rest, so it is positive by construction;
    # a sequential 0..max scale uses the whole colour range instead of throwing
    # half of it away on negatives that never occur.
    vmax = float(np.nanmax([d_mat, d_mat_dn]))
    for ax, M, name in ((axes[0], d_mat, "raw"), (axes[1], d_mat_dn, "neutral-PC denoised")):
        im = ax.imshow(M.T, aspect="auto", cmap="magma", vmin=0, vmax=vmax, interpolation="nearest")
        for yi in range(M.shape[1]):
            for xi in range(L):
                v = M[xi, yi]
                ax.text(
                    xi, yi, f"{v:.1f}", ha="center", va="center", fontsize=5.5,
                    color="white" if v < vmax * 0.62 else "black",
                )
        ax.set_yticks(range(len(targets)))
        ax.set_yticklabels(targets)
        ax.set_xticks(range(0, L, 2))
        ax.set_xticklabels(range(0, L, 2), fontsize=8)
        ax.set_xlabel("hidden_states index (0 = embeddings, 1..N = decoder layers)")
        ax.set_title(f"held-out separation (Cohen's d, in-group vs rest) - {name}", fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    fig.suptitle(
        f"{'/'.join(targets)} direction quality by layer - {label}, {d_mat.shape[0]} hidden states",
        fontsize=12,
    )
    fig.tight_layout()
    p = os.path.join(RESULTS, f"heatmap{tag}.png")
    fig.savefig(p, dpi=140)
    print(f"-> {p}")

    fig2, ax = plt.subplots(figsize=(max(8, L * 0.3), 4.2))
    x = np.arange(L)
    ax.plot(x, acc4, "-o", ms=3, label="diff-of-means")
    ax.plot(x, acc4dn, "-s", ms=3, label="diff-of-means, denoised")
    ax.plot(x, acc4lr, "-^", ms=3, label="logistic regression")
    ax.plot(x, acc4sh, ":", color="grey", label="shuffled-label control")
    nway = len(targets)
    ax.axhline(1.0 / nway, color="k", lw=0.8, ls="--", label=f"chance ({nway}-way)")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("hidden_states index")
    ax.set_ylabel(f"held-out {nway}-way accuracy")
    ax.set_title(f"{'/'.join(targets)} read-out accuracy by layer - {label}")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.25)
    fig2.tight_layout()
    p2 = os.path.join(RESULTS, f"accuracy_by_layer{tag}.png")
    fig2.savefig(p2, dpi=140)
    print(f"-> {p2}")


if __name__ == "__main__":
    sys.exit(main())
