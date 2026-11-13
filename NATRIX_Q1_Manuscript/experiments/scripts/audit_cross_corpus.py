"""Cross-corpus replication of the feature audit (analysis plan §3).

The drop decision is made on CSIC only.  This script repeats the descriptive
part of the audit on SR-BH 2020 and ECML/PKDD 2007 so the paper can show
whether the same signals carry class information in independent corpora.

Protocol (deviation D10): one stratified 80/20 split per corpus, the shipped
200-tree forest trained on the 80%, permutation importance with 5 repeats on
the 20%, and full-corpus univariate statistics with BH correction.  This is a
replication check, not a second selection run: no feature is dropped or added
on the basis of these numbers.

Outputs
-------
experiments/results/feature_audit/cross_corpus_<name>.csv
experiments/results/feature_audit/cross_corpus_summary.json
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import stats_utils as S  # noqa: E402

OUT = C.RESULTS / "feature_audit"
OUT.mkdir(parents=True, exist_ok=True)


def load_corpus(name):
    if name == "srbh":
        z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
        return z["X"], z["y"]
    if name == "ecml":
        records = C.load_ecml_records()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        return X, C.label_array(records)
    raise ValueError(name)


def cliffs_delta(clean, attack) -> float:
    """Cliff's delta via the Mann-Whitney U statistic (no O(n^2) loop)."""
    n1, n2 = len(clean), len(attack)
    if n1 == 0 or n2 == 0:
        return 0.0
    u = mannwhitneyu(clean, attack, alternative="two-sided").statistic
    return float(2.0 * u / (n1 * n2) - 1.0)


def bh(pvalues) -> np.ndarray:
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    m = len(p)
    adjusted = ranked * m / (np.arange(m) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    out = np.empty_like(adjusted)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    return out


def audit(name: str) -> pd.DataFrame:
    started = time.time()
    X, y = load_corpus(name)
    print(f"{name}: X={X.shape} labels={np.bincount(y).tolist()}", flush=True)

    rows = []
    for j, feature in enumerate(C.FEATURES):
        col = X[:, j]
        clean, attack = col[y == 0], col[y == 1]
        if np.std(col) > 0:
            p = float(mannwhitneyu(clean, attack, alternative="two-sided").pvalue)
        else:
            p = 1.0
        rows.append({
            "feature": feature,
            "clean_mean": float(clean.mean()),
            "attack_mean": float(attack.mean()),
            "clean_zero_frac": float(np.mean(clean == 0)),
            "attack_zero_frac": float(np.mean(attack == 0)),
            "p_value": p,
            "cliffs_delta": cliffs_delta(clean, attack),
        })
    frame = pd.DataFrame(rows)
    frame["p_bh"] = bh(frame["p_value"].values)

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=C.SEED
    )
    model = C.make_rf()
    model.fit(Xtr, ytr)
    perm = permutation_importance(
        model, Xte, yte, n_repeats=5, random_state=C.SEED,
        scoring="accuracy", n_jobs=1,
    )
    frame["gini_importance"] = model.feature_importances_
    frame["perm_importance_mean"] = perm.importances_mean
    frame["perm_importance_std"] = perm.importances_std
    frame["perm_rank"] = frame["perm_importance_mean"].rank(ascending=False).astype(int)
    frame["corpus"] = name
    frame["n"] = len(y)
    frame["elapsed_s"] = round(time.time() - started, 1)
    frame.sort_values("perm_importance_mean", ascending=False).to_csv(
        OUT / f"cross_corpus_{name}.csv", index=False
    )
    print(frame[["feature", "cliffs_delta", "p_bh", "gini_importance",
                 "perm_importance_mean"]].sort_values(
        "perm_importance_mean", ascending=False).to_string(index=False), flush=True)
    return frame


def main() -> None:
    frames = [audit(name) for name in ("ecml", "srbh")]
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(OUT / "cross_corpus_all.csv", index=False)
    C.write_json(OUT / "cross_corpus_summary.json", {
        "protocol": "stratified 80/20; shipped RF; permutation 5 repeats; full univariate",
        "deviation": "D10",
        "corpora": {name: int((combined["corpus"] == name).sum()) for name in ("ecml", "srbh")},
        "results": combined.to_dict("records"),
    })
    print(combined.groupby("corpus")["n"].first().to_string())


if __name__ == "__main__":
    main()
