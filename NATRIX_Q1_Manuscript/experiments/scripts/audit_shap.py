"""SHAP audit on a bounded sample.

Kept separate from audit_model.py so a slow explainer cannot block the main
audit.  500 records per fold, tree-path-dependent explainer, one thread.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "feature_audit"
OUT.mkdir(parents=True, exist_ok=True)
SAMPLE = 500


def main() -> None:
    import shap

    records, _ = C.csic_unique()
    X, _ = C.extract_matrix(records)
    y = C.label_array(records)
    names = C.FEATURES

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=C.SEED)
    rows = []
    started = time.time()

    for fold, (tr, te) in enumerate(skf.split(X, y)):
        model = C.make_rf().fit(X[tr], y[tr])
        rng = np.random.default_rng(C.SEED + fold)
        idx = rng.choice(te, size=min(SAMPLE, len(te)), replace=False)
        explainer = shap.TreeExplainer(model, feature_perturbation="tree_path_dependent")
        values = explainer.shap_values(X[idx], check_additivity=False)
        if isinstance(values, list):
            values = values[1]
        values = np.asarray(values)
        if values.ndim == 3:
            values = values[:, :, 1]
        mean_abs = np.abs(values).mean(axis=0)
        for j, name in enumerate(names):
            rows.append({"fold": fold, "feature": name, "mean_abs_shap": float(mean_abs[j])})
        print(f"fold {fold}: {time.time() - started:.1f}s", flush=True)

    frame = pd.DataFrame(rows)
    agg = frame.groupby("feature")["mean_abs_shap"].agg(["mean", "std"]).reset_index()
    agg.columns = ["feature", "mean_abs_shap_mean", "mean_abs_shap_std"]
    agg.sort_values("mean_abs_shap_mean", ascending=False).to_csv(OUT / "csic_shap_importance.csv", index=False)
    frame.to_csv(OUT / "csic_shap_raw.csv", index=False)
    print(agg.to_string(index=False))


if __name__ == "__main__":
    main()
