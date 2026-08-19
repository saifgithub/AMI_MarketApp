#!/usr/bin/env python3
"""sa_fdr.py — simulated-annealing subset search with a Fisher-discriminant-ratio
objective (SA-FDR, arXiv 2507.23568; CR196 §2 "mixture/feature optimization").

Generic module, two consumers:

(a) RECIPE-LEVEL feature selection (runs on the build box, no model needed):
    given per-example feature vectors X and class labels y from a recipe's _meta,
    find the feature subset maximizing multi-class FDR — trace(S_between)/trace(S_within)
    on the selected columns. Recipes use the result to decide which brief fields carry
    discriminative signal.

(b) MIX-LEVEL weight search (runs on the TRAINING box — the objective needs model
    embeddings or short LoRA probes; this module only supplies the SA loop, the caller
    supplies `objective(subset_or_weights)`; probe budget capped by max_evals).

The SA loop is deliberately standard: bit-flip neighborhood, geometric cooling,
accept-worse with exp(delta/T), deterministic seed. No dependencies beyond numpy.
"""
import math

import numpy as np


def fisher_discriminant_ratio(X, y, cols):
    """Multi-class Fisher criterion J = trace(Sw^-1 Sb) on the selected columns.
    Unlike the scalar trace-ratio, J is ~additive over independent informative
    features and discounts redundant ones — so a weaker-but-complementary feature
    raises the score instead of diluting it. Regularized inverse; degenerate → 0."""
    cols = np.asarray(sorted(cols))
    if cols.size == 0:
        return 0.0
    Xs = X[:, cols]
    classes = np.unique(y)
    if classes.size < 2:
        return 0.0
    d = Xs.shape[1]
    mu = Xs.mean(axis=0)
    Sb = np.zeros((d, d))
    Sw = np.zeros((d, d))
    for c in classes:
        Xc = Xs[y == c]
        if len(Xc) == 0:
            continue
        muc = Xc.mean(axis=0)
        dm = (muc - mu)[:, None]
        Sb += len(Xc) * (dm @ dm.T)
        Xd = Xc - muc
        Sw += Xd.T @ Xd
    Sw += 1e-6 * np.trace(Sw) / max(d, 1) * np.eye(d)  # ridge for stability
    try:
        return float(np.trace(np.linalg.solve(Sw, Sb)))
    except np.linalg.LinAlgError:
        return 0.0


def anneal(n_items, objective, *, max_evals=2000, t0=1.0, cooling=0.995,
           init=None, seed=42, penalty_per_item=0.0):
    """Maximize objective(frozenset of selected indices) over subsets of range(n_items).

    penalty_per_item > 0 rewards compactness (the l0 pressure in SA-FDR).
    Returns (best_subset, best_score, history) — history is [(eval#, score)] at
    improvements, for the report.
    """
    rng = np.random.default_rng(seed)
    cur = set(init) if init is not None else set(range(n_items))
    def scored(s):
        return objective(frozenset(s)) - penalty_per_item * len(s)
    cur_score = scored(cur)
    best, best_score = set(cur), cur_score
    history = [(0, best_score)]
    t = t0
    for i in range(1, max_evals):
        cand = set(cur)
        flip = int(rng.integers(n_items))
        (cand.remove if flip in cand else cand.add)(flip)
        if not cand:
            continue
        s = scored(cand)
        if s >= cur_score or rng.random() < math.exp((s - cur_score) / max(t, 1e-9)):
            cur, cur_score = cand, s
            if s > best_score:
                best, best_score = set(cand), s
                history.append((i, s))
        t *= cooling
    return frozenset(best), best_score, history


def select_features(X, y, feature_names, *, max_evals=2000, penalty=0.001, seed=42):
    """Consumer (a): returns (selected_names, fdr_all, fdr_selected, history)."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y)
    keep = ~np.isnan(X).any(axis=0)
    X, names = X[:, keep], [n for n, k in zip(feature_names, keep) if k]
    # z-score so trace-FDR isn't dominated by scale
    std = X.std(axis=0)
    std[std < 1e-12] = 1.0
    X = (X - X.mean(axis=0)) / std
    fdr_all = fisher_discriminant_ratio(X, y, range(X.shape[1]))
    subset, score, hist = anneal(
        X.shape[1], lambda s: fisher_discriminant_ratio(X, y, s),
        max_evals=max_evals, penalty_per_item=penalty, seed=seed)
    return ([names[i] for i in sorted(subset)], fdr_all,
            fisher_discriminant_ratio(X, y, subset), hist)
