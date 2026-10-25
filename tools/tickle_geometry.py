#!/usr/bin/env python3
"""Phase seven, CPU side - readouts and geometry for the tickle / itch directions.

Inputs (all produced by the existing pipeline, nothing re-fitted by hand):
  data/acts_sens_tickle.npz        extract.py, groups warm,cold,pain,neutral,tickle,itch
  data/directions_sens_tickle.npz  analyze.py on that, targets = the five sensations
  data/acts.npz / directions.npz           phase one (four emotions + neutral)
  data/acts_sens.npz / directions_sens.npz phase three (warm/cold/pain + neutral)

Group order puts neutral FOURTH on purpose: analyze.split_indices shuffles group by
group from one RNG stream, so with warm, cold, pain, neutral first the held-out
split of those four groups is identical to phase three's (checked below), and the
re-derived warm/cold/pain can be compared against the stored ones like for like.

Readouts (held-out, difference-of-means exactly as analyze.py: d_g = mean(train g)
- mean(train of every group in the fit), unit, argmax over the fit's targets):
  tickle vs neutral, itch vs neutral         (2-way, chance 0.5)
  tickle vs itch (neutral in the centre)     (2-way, chance 0.5)
  warm/cold/pain/tickle (+neutral centre)    (4-way, chance 0.25)  <- the task's
  warm/cold/pain/itch                        (4-way)
  all five sensations                        (5-way, chance 0.2)
Each with a shuffled-training-label floor (50 permutations at the lever layer,
one per layer for the curve) and a logistic-regression control at the lever.

Geometry at the lever layer: raw and partialled cosines (each corpus's own
generic axis projected out, BUILD_REPORT_3 sec 3.1) of tickle / itch against the
four emotions, against the stored phase-three warm/cold/pain, within the new
five-sensation frame, and tickle vs itch. Plus a bootstrap over passages for the
partialled cosines, and a "fit without the other new group" robustness check.

CPU + numpy (+ sklearn for the logistic control).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from analyze import emotion_accuracy, fit_layer, split_indices, unit
from dir_cosine import cos, generic_axis, partial

EMO_G = ["happy", "sad", "angry", "fearful", "neutral"]
EMOS = ["happy", "sad", "angry", "fearful"]
S3_G = ["warm", "cold", "pain", "neutral"]
S3 = ["warm", "cold", "pain"]
NEW_G = ["warm", "cold", "pain", "neutral", "tickle", "itch"]
SENS5 = ["warm", "cold", "pain", "tickle", "itch"]

READOUTS = [
    ("tickle_vs_neutral", ["tickle", "neutral"], ["tickle", "neutral"]),
    ("itch_vs_neutral", ["itch", "neutral"], ["itch", "neutral"]),
    ("tickle_vs_itch", ["tickle", "itch", "neutral"], ["tickle", "itch"]),
    ("wcp_tickle_4way", ["warm", "cold", "pain", "tickle", "neutral"], ["warm", "cold", "pain", "tickle"]),
    ("wcp_itch_4way", ["warm", "cold", "pain", "itch", "neutral"], ["warm", "cold", "pain", "itch"]),
    ("sens5_5way", NEW_G, SENS5),
]


def rows_of(labels, idx, groups_all, fit_groups):
    keep = [groups_all.index(g) for g in fit_groups]
    return idx[np.isin(labels[idx], keep)]


def readout_acc(A, labels, tr, te, groups_all, targets):
    _, _, pt, _ = fit_layer(A, labels, tr, te, groups=groups_all, targets=targets)
    return emotion_accuracy(pt, labels[te], groups_all, targets), pt


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort() + 1.0
    rp = ranks[: len(pos)].sum()
    return float((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def logreg(A, labels, tr, te, groups_all, targets, seed):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    ids = [groups_all.index(t) for t in targets]
    tr = tr[np.isin(labels[tr], ids)]
    te = te[np.isin(labels[te], ids)]
    sc = StandardScaler().fit(A[tr])
    clf = LogisticRegression(max_iter=3000, C=0.1, random_state=seed).fit(sc.transform(A[tr]), labels[tr])
    return float(clf.score(sc.transform(A[te]), labels[te]))


def fit_dirs(A, labels, tr, groups_all, fit_groups, targets):
    """Directions + generic axis for one fit, from training rows only."""
    trf = rows_of(labels, tr, groups_all, fit_groups)
    X, y = A[trf], labels[trf]
    grand = X.mean(0)
    D = {t: unit(X[y == groups_all.index(t)].mean(0) - grand) for t in targets}
    tgt = np.isin(y, [groups_all.index(t) for t in targets])
    ga = unit(X[tgt].mean(0) - grand)
    return D, ga


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--acts", default=os.path.join(ROOT, "data", "acts_sens_tickle.npz"))
    ap.add_argument("--dirs", default=os.path.join(ROOT, "data", "directions_sens_tickle.npz"))
    ap.add_argument("--layer", type=int, default=17)
    ap.add_argument("--holdout", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--n-perm", type=int, default=50)
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--json-out", default=os.path.join(ROOT, "results", "tickle_geometry.json"))
    args = ap.parse_args()
    k = args.layer
    D_ = os.path.join(ROOT, "data")

    z = np.load(args.acts, allow_pickle=True)
    acts, labels = z["acts"], z["labels"]
    groups = [str(x) for x in z["groups"]]
    if groups != NEW_G:
        raise SystemExit(f"{args.acts} groups {groups} != {NEW_G}")
    L = acts.shape[0]
    train, test = split_indices(labels, args.holdout, args.seed, groups)
    out: dict = {"layer": k, "groups": groups, "n_train": len(train), "n_test": len(test),
                 "counts": {g: int((labels == i).sum()) for i, g in enumerate(groups)}}
    print(f"[data] {acts.shape}; counts {out['counts']}; train {len(train)} / test {len(test)}")

    # --- split identity with phase three ---------------------------------------
    z3 = np.load(os.path.join(D_, "acts_sens.npz"), allow_pickle=True)
    tr3, te3 = split_indices(z3["labels"], args.holdout, args.seed, S3_G)
    ids3, idsn = z3["ids"], z["ids"]
    same = sorted(map(str, ids3[te3])) == sorted(str(x) for x in idsn[test] if not str(x).startswith(("tickle", "itch")))
    out["holdout_identical_to_phase3_for_wcpn"] = bool(same)
    print(f"[split] held-out ids for warm/cold/pain/neutral identical to phase three: {same}")
    # neutral activations, two independent Windows forwards
    n3 = z3["acts"][k][z3["labels"] == S3_G.index("neutral")]
    nn = acts[k][labels == groups.index("neutral")]
    rel = np.linalg.norm(n3 - nn, axis=1) / np.linalg.norm(n3, axis=1)
    out["neutral_rerun_rel_l2_hs"] = {"mean": float(rel.mean()), "max": float(rel.max())}
    print(f"[rerun] neutral hs{k} per-passage relative L2 vs phase three: mean {rel.mean():.2e} max {rel.max():.2e}")

    # --- readouts ----------------------------------------------------------------
    rng = np.random.default_rng(args.seed + 1)
    rd: dict = {}
    for name, fit_groups, targets in READOUTS:
        tr = rows_of(labels, train, groups, fit_groups)
        te = rows_of(labels, test, groups, fit_groups)
        curve, floor_curve = [], []
        for layer in range(L):
            A = acts[layer]
            acc, _ = readout_acc(A, labels, tr, te, groups, targets)
            sh = labels.copy()
            sh[tr] = rng.permutation(labels[tr])
            facc, _ = readout_acc(A, sh, tr, te, groups, targets)
            curve.append(acc)
            floor_curve.append(facc)
        A = acts[k]
        acc_k, pt = readout_acc(A, labels, tr, te, groups, targets)
        perms = []
        for _ in range(args.n_perm):
            sh = labels.copy()
            sh[tr] = rng.permutation(labels[tr])
            perms.append(readout_acc(A, sh, tr, te, groups, targets)[0])
        lr = logreg(A, labels, tr, te, groups, targets, args.seed)
        tgt_te = te[np.isin(labels[te], [groups.index(t) for t in targets])]
        rec = {
            "targets": targets, "fit_groups": fit_groups, "chance": 1 / len(targets),
            "n_test": len(tgt_te),
            "acc_at_lever": acc_k, "logreg_at_lever": lr,
            "perm_floor_at_lever_mean": float(np.mean(perms)), "perm_floor_at_lever_p95": float(np.percentile(perms, 95)),
            "perm_floor_at_lever_max": float(np.max(perms)),
            "peak": {"layer": int(np.argmax(curve)), "acc": float(np.max(curve))},
            "curve": [round(float(x), 4) for x in curve],
            "floor_curve_mean": float(np.mean(floor_curve)), "floor_curve_max": float(np.max(floor_curve)),
        }
        if len(targets) == 2:
            # threshold-free separation on the first target's direction
            m = labels[tgt_te] == groups.index(targets[0])
            sc = pt[np.isin(labels[te], [groups.index(t) for t in targets])][:, 0]
            rec["auc_at_lever"] = auc(sc[m], sc[~m])
        else:
            # confusion matrix at the lever
            ids = [groups.index(t) for t in targets]
            mask = np.isin(labels[te], ids)
            pred = pt[mask].argmax(1)
            true = np.array([ids.index(v) for v in labels[te][mask]])
            rec["confusion"] = {targets[i]: {targets[j]: int(((true == i) & (pred == j)).sum()) for j in range(len(targets))}
                                for i in range(len(targets))}
        rd[name] = rec
        print(f"[readout] {name:<18} hs{k} acc={acc_k:.3f} (n={len(tgt_te)}, chance {1 / len(targets):.2f}) "
              f"logreg={lr:.3f} perm floor mean={np.mean(perms):.3f} p95={np.percentile(perms, 95):.3f} "
              f"| peak {np.max(curve):.3f}@hs{int(np.argmax(curve))}" + (f" AUC={rec['auc_at_lever']:.3f}" if "auc_at_lever" in rec else ""))
    out["readouts"] = rd

    # --- directions ---------------------------------------------------------------
    zt = np.load(args.dirs, allow_pickle=True)
    names_t = [str(x) for x in zt["emotions"]]
    if names_t != SENS5:
        raise SystemExit(f"{args.dirs} rows {names_t} != {SENS5}")
    ze = np.load(os.path.join(D_, "directions.npz"), allow_pickle=True)
    zs = np.load(os.path.join(D_, "directions_sens.npz"), allow_pickle=True)
    ga_t = generic_axis(args.acts, NEW_G, SENS5, args.holdout, args.seed)
    ga_e = generic_axis(os.path.join(D_, "acts.npz"), EMO_G, EMOS, args.holdout, args.seed)
    ga_s = generic_axis(os.path.join(D_, "acts_sens.npz"), S3_G, S3, args.holdout, args.seed)
    out["generic_axis_recomputed_vs_stored"] = float(ga_t[k] @ unit(zt["generic_axis"][k]))

    T = {n: zt["dirs_raw"][k, i] for i, n in enumerate(names_t)}
    E = {n: ze["dirs_raw"][k, i] for i, n in enumerate(EMOS)}
    S = {n: zs["dirs_raw"][k, i] for i, n in enumerate(S3)}
    Tp = {n: partial(v, ga_t[k]) for n, v in T.items()}
    Ep = {n: partial(v, ga_e[k]) for n, v in E.items()}
    Sp = {n: partial(v, ga_s[k]) for n, v in S.items()}

    geo: dict = {
        "floor_new_vs_emotion": cos(ga_t[k], ga_e[k]),
        "floor_new_vs_phase3": cos(ga_t[k], ga_s[k]),
        "floor_phase3_vs_emotion": cos(ga_s[k], ga_e[k]),
        "axis_load_new": {n: float(unit(T[n]) @ unit(ga_t[k])) for n in names_t},
        "rederived_vs_stored_phase3": {n: cos(T[n], S[n]) for n in S3},
        "rederived_vs_stored_phase3_partial": {n: cos(Tp[n], Sp[n]) for n in S3},
        "vs_emotion_raw": {r: {c: cos(T[r], E[c]) for c in EMOS} for r in names_t},
        "vs_emotion_partial": {r: {c: cos(Tp[r], Ep[c]) for c in EMOS} for r in names_t},
        "vs_phase3_raw": {r: {c: cos(T[r], S[c]) for c in S3} for r in names_t},
        "vs_phase3_partial": {r: {c: cos(Tp[r], Sp[c]) for c in S3} for r in names_t},
        "within_new_raw": {r: {c: cos(T[r], T[c]) for c in names_t} for r in names_t},
        "within_new_partial": {r: {c: cos(Tp[r], Tp[c]) for c in names_t} for r in names_t},
        "stored_phase3_vs_emotion_partial": {r: {c: cos(Sp[r], Ep[c]) for c in EMOS} for r in S3},
    }

    # robustness: fit each new direction WITHOUT the other new group in the centre
    rob = {}
    for new, other in (("tickle", "itch"), ("itch", "tickle")):
        fg = [g for g in NEW_G if g != other]
        tg = [g for g in SENS5 if g != other]
        Dx, gax = fit_dirs(acts[k], labels, train, groups, fg, tg)
        rob[new] = {
            "cos_with_joint_fit": cos(Dx[new], T[new]),
            "vs_emotion_partial": {c: cos(partial(Dx[new], gax), Ep[c]) for c in EMOS},
            "vs_phase3_partial": {c: cos(partial(Dx[new], gax), Sp[c]) for c in S3},
        }
    geo["fit_without_other_new_group"] = rob

    # probe in an existing frame: the new group's train mean minus THAT frame's
    # train grand mean, partialled with THAT frame's generic axis. "Where would
    # tickle have landed if it had been measured in phase three's coordinates."
    # Within the joint frame the partialled directions are linearly dependent by
    # construction (their count-weighted sum is exactly zero once the generic axis
    # is removed), so within-frame partial cosines sit on a negative baseline of
    # about -1/(n_targets - 1). Cross-frame and probe cosines have no such tie.
    tr3_rows = tr3
    G3 = z3["acts"][k][tr3_rows].mean(0)
    ze_a = np.load(os.path.join(D_, "acts.npz"), allow_pickle=True)
    tre_rows, _ = split_indices(ze_a["labels"], args.holdout, args.seed, EMO_G)
    GE = ze_a["acts"][k][tre_rows].mean(0)
    probe = {}
    for new in ("tickle", "itch"):
        mu = acts[k][train][labels[train] == groups.index(new)].mean(0)
        d3 = partial(unit(mu - G3), ga_s[k])
        dE = partial(unit(mu - GE), ga_e[k])
        probe[new] = {
            "phase3_frame_partial": {c: cos(d3, Sp[c]) for c in S3},
            "emotion_frame_partial": {c: cos(dE, Ep[c]) for c in EMOS},
            "phase3_frame_raw": {c: cos(unit(mu - G3), S[c]) for c in S3},
        }
    probe["tickle*itch_phase3_frame_partial"] = cos(
        partial(unit(acts[k][train][labels[train] == groups.index("tickle")].mean(0) - G3), ga_s[k]),
        partial(unit(acts[k][train][labels[train] == groups.index("itch")].mean(0) - G3), ga_s[k]),
    )
    # calibration for the emotion-frame probe: the same measurement on the three
    # phase-three groups, whose cross-frame answer is known (warm->happy,
    # cold->fearful, pain->angry). If the probe gives fearful to everything, the
    # probe is reading the corpus template, not the sensation.
    probe["emotion_frame_calibration"] = {}
    for g in S3:
        mu = acts[k][train][labels[train] == groups.index(g)].mean(0)
        dE = partial(unit(mu - GE), ga_e[k])
        probe["emotion_frame_calibration"][g] = {c: cos(dE, Ep[c]) for c in EMOS}
    n_t = len(SENS5)
    geo["within_frame_partial_baseline"] = -1 / (n_t - 1)
    geo["probe_in_existing_frame"] = probe

    # bootstrap over training passages (both corpora resampled within group)
    ze_acts = np.load(os.path.join(D_, "acts.npz"), allow_pickle=True)
    Ae, le = ze_acts["acts"][k], ze_acts["labels"]
    tre, _ = split_indices(le, args.holdout, args.seed, EMO_G)
    zs_acts = z3
    As, ls = zs_acts["acts"][k], zs_acts["labels"]
    brng = np.random.default_rng(20261025)

    def resample(idx, lab):
        parts = []
        for g in np.unique(lab[idx]):
            gi = idx[lab[idx] == g]
            parts.append(brng.choice(gi, size=len(gi), replace=True))
        return np.concatenate(parts)

    keys = [("tickle", "happy"), ("tickle", "sad"), ("tickle", "angry"), ("tickle", "fearful"),
            ("itch", "happy"), ("itch", "sad"), ("itch", "angry"), ("itch", "fearful")]
    keys3 = [("tickle", "warm"), ("tickle", "cold"), ("tickle", "pain"), ("itch", "warm"), ("itch", "cold"), ("itch", "pain")]
    boot = {f"{a}*{b}": [] for a, b in keys + keys3}
    boot["tickle*itch"] = []
    At = acts[k]
    for _ in range(args.n_boot):
        bt = resample(train, labels)
        be = resample(tre, le)
        bs = resample(tr3, ls)
        Dt, gt = fit_dirs(At, labels, bt, groups, NEW_G, SENS5)
        De, gE = fit_dirs(Ae, le, be, EMO_G, EMO_G, EMOS)
        Ds, gS = fit_dirs(As, ls, bs, S3_G, S3_G, S3)
        for a, b in keys:
            boot[f"{a}*{b}"].append(cos(partial(Dt[a], gt), partial(De[b], gE)))
        for a, b in keys3:
            boot[f"{a}*{b}"].append(cos(partial(Dt[a], gt), partial(Ds[b], gS)))
        boot["tickle*itch"].append(cos(partial(Dt["tickle"], gt), partial(Dt["itch"], gt)))
    geo["bootstrap_partial"] = {
        kk: {"mean": float(np.mean(v)), "lo95": float(np.percentile(v, 2.5)), "hi95": float(np.percentile(v, 97.5))}
        for kk, v in boot.items()
    }
    geo["bootstrap_n"] = args.n_boot

    # per-layer profiles (raw and partial)
    prof_pairs = [("tickle", "happy", "E"), ("tickle", "pain", "S"), ("tickle", "warm", "S"),
                  ("itch", "pain", "S"), ("itch", "angry", "E"), ("tickle", "itch", "T")]
    prof = {}
    for a, b, src in prof_pairs:
        raw_l, par_l = [], []
        for layer in range(L):
            ta = zt["dirs_raw"][layer, names_t.index(a)]
            if src == "E":
                tb, gb = ze["dirs_raw"][layer, EMOS.index(b)], ga_e[layer]
            elif src == "S":
                tb, gb = zs["dirs_raw"][layer, S3.index(b)], ga_s[layer]
            else:
                tb, gb = zt["dirs_raw"][layer, names_t.index(b)], ga_t[layer]
            raw_l.append(round(cos(ta, tb), 4))
            par_l.append(round(cos(partial(ta, ga_t[layer]), partial(tb, gb)), 4))
        prof[f"{a}*{b}"] = {"raw": raw_l, "partial": par_l}
    geo["per_layer"] = prof
    out["geometry"] = geo

    def show(title, M, rows, cols):
        print(f"\n  {title}")
        print("  " + " " * 8 + "".join(f"{c:>9}" for c in cols))
        for r in rows:
            print(f"  {r:<8}" + "".join(f"{M[r][c]:>+9.3f}" for c in cols))

    print(f"\n=== geometry hs{k} ===")
    print(f"  floors: new-vs-emotion {geo['floor_new_vs_emotion']:+.3f}  new-vs-phase3 {geo['floor_new_vs_phase3']:+.3f}  "
          f"phase3-vs-emotion {geo['floor_phase3_vs_emotion']:+.3f}")
    print(f"  load on own generic axis: {geo['axis_load_new']}")
    print(f"  re-derived w/c/p vs stored: raw {geo['rederived_vs_stored_phase3']}  partial {geo['rederived_vs_stored_phase3_partial']}")
    show("vs emotions RAW", geo["vs_emotion_raw"], names_t, EMOS)
    show("vs emotions PARTIAL", geo["vs_emotion_partial"], names_t, EMOS)
    show("vs stored phase-3 sensations RAW", geo["vs_phase3_raw"], names_t, S3)
    show("vs stored phase-3 sensations PARTIAL", geo["vs_phase3_partial"], names_t, S3)
    show("within new frame RAW", geo["within_new_raw"], names_t, names_t)
    show("within new frame PARTIAL", geo["within_new_partial"], names_t, names_t)
    print(f"\n  robustness (fit without the other new group): {json.dumps(rob, indent=None)}")
    print(f"\n  probe in existing frames: {json.dumps(probe, indent=None)}")
    print("\n  bootstrap partial cosines (mean [95%]):")
    for kk, v in geo["bootstrap_partial"].items():
        print(f"    {kk:<16} {v['mean']:+.3f} [{v['lo95']:+.3f}, {v['hi95']:+.3f}]")

    with open(args.json_out, "w") as f:
        json.dump(out, f, indent=1)
    print(f"\n-> {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
