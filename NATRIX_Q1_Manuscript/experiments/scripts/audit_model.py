"""Multivariate audit of the 22 v3 features on CSIC 2010.

Per outer fold (deployment-like stratified split over unique requests):
  * permutation importance on the held-out fold (single-threaded: joblib
    workers deadlock with shap/RF on Windows)
  * mutual information on the training fold
  * L1-logistic selection frequency over bootstrap resamples of the training fold

SHAP is a separate script (audit_shap.py) so a slow explainer cannot block the
rest of the audit.

Writes out-of-fold probabilities for the full 22-D model, reused by calibration
and ablation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "feature_audit"
OUT.mkdir(parents=True, exist_ok=True)

N_SPLITS = 5
N_BOOTSTRAP_L1 = 100
# Mutual information and bootstrap L1 are estimated on a training-fold
# subsample: exact KNN MI is quadratic-ish at 27k rows and the bootstrap does
# not need every row to estimate selection frequency.  Permutation importance
# and SHAP still use the full held-out fold.  Recorded as deviation D4.
SAMPLE = 8000


def main() -> None:
    records, _ = C.csic_unique()
    X, _ = C.extract_matrix(records)
    y = C.label_array(records)
    names = C.FEATURES

    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=C.SEED)
    folds = list(skf.split(X, y))
    C.write_json(
        OUT / "folds.json",
        {"n_splits": N_SPLITS, "seed": C.SEED, "protocol": "P1 stratified unique",
         "test_indices": [te.tolist() for _, te in folds]},
    )

    perm_records, mi_records, stability_records = [], [], []
    oof = np.zeros(len(y), dtype=float)

    vif_rows = []
    Xz = StandardScaler().fit_transform(X)
    for j, name in enumerate(names):
        try:
            value = float(variance_inflation_factor(Xz, j))
        except Exception:  # noqa: BLE001
            value = float("inf")
        vif_rows.append({"feature": name, "vif": value})
    pd.DataFrame(vif_rows).to_csv(OUT / "vif.csv", index=False)
    print("VIF done", flush=True)

    started = time.time()
    for fold, (tr, te) in enumerate(folds):
        model = C.make_rf().fit(X[tr], y[tr])
        oof[te] = model.predict_proba(X[te])[:, 1]
        print(f"  fold {fold}: model fitted ({time.time() - started:.1f}s)", flush=True)

        perm = permutation_importance(
            model, X[te], y[te], n_repeats=10, random_state=C.SEED, n_jobs=1
        )
        for j, name in enumerate(names):
            perm_records.append({
                "fold": fold, "feature": name,
                "importance_mean": float(perm.importances_mean[j]),
                "importance_std": float(perm.importances_std[j]),
            })
        print(f"  fold {fold}: permutation done ({time.time() - started:.1f}s)", flush=True)

        rng = np.random.default_rng(C.SEED + fold)
        sample = rng.choice(tr, size=min(SAMPLE, len(tr)), replace=False)
        mi = mutual_info_classif(
            X[sample], y[sample], discrete_features="auto",
            random_state=C.SEED, n_jobs=1,
        )
        for j, name in enumerate(names):
            mi_records.append({"fold": fold, "feature": name, "mutual_info": float(mi[j])})
        print(f"  fold {fold}: mutual information done ({time.time() - started:.1f}s)", flush=True)

        scaler = StandardScaler().fit(X[sample])
        Xtr = scaler.transform(X[sample])
        ytr = y[sample]
        rng = np.random.default_rng(C.SEED + 100 + fold)
        counts = np.zeros(len(names))
        for _ in range(N_BOOTSTRAP_L1):
            idx = rng.integers(0, len(sample), len(sample))
            if len(np.unique(ytr[idx])) < 2:
                continue
            l1 = LogisticRegression(
                penalty="l1", C=0.5, solver="liblinear", max_iter=2000
            ).fit(Xtr[idx], ytr[idx])
            counts += (np.abs(l1.coef_[0]) > 1e-8).astype(float)
        for j, name in enumerate(names):
            stability_records.append({
                "fold": fold, "feature": name,
                "selection_frequency": counts[j] / N_BOOTSTRAP_L1,
            })
        print(f"  fold {fold}: L1 stability done ({time.time() - started:.1f}s)", flush=True)

    np.savez(OUT / "csic_oof_full.npz", oof=oof, y=y)

    def aggregate(records, value_col, out_col):
        frame = pd.DataFrame(records)
        agg = frame.groupby("feature")[value_col].agg(["mean", "std", "min", "max"]).reset_index()
        agg.columns = ["feature", f"{out_col}_mean", f"{out_col}_std", f"{out_col}_min", f"{out_col}_max"]
        return agg

    merged = (
        aggregate(perm_records, "importance_mean", "importance")
        .merge(aggregate(mi_records, "mutual_info", "mutual_info"), on="feature")
        .merge(aggregate(stability_records, "selection_frequency", "selection_frequency"), on="feature")
        .merge(pd.read_csv(OUT / "vif.csv"), on="feature")
    )
    merged["perm_rank"] = merged["importance_mean"].rank(ascending=False)
    merged = merged.sort_values("importance_mean", ascending=False)
    merged.to_csv(OUT / "csic_model_importance.csv", index=False)

    pd.DataFrame(perm_records).to_csv(OUT / "csic_permutation_raw.csv", index=False)
    pd.DataFrame(mi_records).to_csv(OUT / "csic_mutual_info_raw.csv", index=False)
    pd.DataFrame(stability_records).to_csv(OUT / "csic_stability_raw.csv", index=False)

    print(merged[["feature", "importance_mean", "mutual_info_mean",
                  "selection_frequency_mean", "vif"]].to_string(index=False))


if __name__ == "__main__":
    main()
