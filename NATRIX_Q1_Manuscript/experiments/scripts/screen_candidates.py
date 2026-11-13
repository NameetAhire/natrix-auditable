"""Screen the 24 pre-registered v4 candidates with nested cross-validation.

Protocol (feature_candidates.md):
  1. drop candidates near-constant on every corpus;
  2. drop candidates with |Spearman| >= 0.95 against a retained feature;
  3. inside each outer training fold, compare core+C against core with an inner
     cross-validation, and accept C only if its mean F1 gain exceeds its own
     standard error;
  4. v4 = retained v3 core + accepted candidates.

Deviation D5: the screening stage uses 3 inner folds and 100 trees to keep the
search inside the 8 GB / single-workstation budget. The final v3-vs-v4
comparison uses the full protocol configuration (5 inner folds, 200 trees).

Outputs
-------
experiments/results/v4_screening/candidate_screening.csv
experiments/results/v4_screening/candidate_univariate.csv
artifacts/feature_selection/v4_definition.json
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import candidate_features as CF  # noqa: E402

OUT = C.RESULTS / "v4_screening"
OUT.mkdir(parents=True, exist_ok=True)

N_TREES = 100
INNER_SPLITS = 3
CORR_LIMIT = 0.95


def candidate_matrix(records) -> np.ndarray:
    return np.asarray([CF.extract(rec) for rec in records], dtype=np.float32)


def near_constant(col: np.ndarray) -> bool:
    return bool(np.std(col) == 0 or np.mean(col == 0) >= 0.99)


def main() -> None:
    started = time.time()
    records, _ = C.csic_unique()
    X = C.extract_matrix(records, dtype=np.float32)[0]
    Cmat = candidate_matrix(records)
    X_all = np.hstack([X, Cmat])
    cand_offset = X.shape[1]
    y = C.label_array(records)
    names = list(C.FEATURES)
    cand_names = list(CF.CANDIDATE_NAMES)

    # ---- corpus availability for the near-constant rule -----------------
    corpora = {"csic": (Cmat, y)}
    srbh_path = C.PROCESSED / "srbh" / "srbh_features.npz"
    if srbh_path.exists():
        z = np.load(srbh_path, allow_pickle=True)
        if "C" in z:
            corpora["srbh"] = (z["C"], z["y"])
    wcp_path = C.PROCESSED / "openappsec" / "wcp_features.npz"
    if wcp_path.exists():
        z = np.load(wcp_path, allow_pickle=True)
        if "C" in z:
            corpora["wcp"] = (z["C"], z["y"])

    constant_rows = []
    for j, name in enumerate(cand_names):
        flags = {corpus: near_constant(matrix[:, j]) for corpus, (matrix, _) in corpora.items()}
        constant_rows.append({"candidate": name, **flags, "all_constant": all(flags.values())})
    const_frame = pd.DataFrame(constant_rows)

    # ---- correlation filter against retained core -----------------------
    core_path = C.ARTIFACTS / "feature_selection" / "v4_core.json"
    if core_path.exists():
        core = C.read_json(core_path)["retained_core"]
    else:
        core = names
        print("WARNING: v4_core.json missing; using all 22 v3 features as core")
    core_idx = [names.index(name) for name in core]
    core_matrix = X[:, core_idx]

    corr_rows = []
    keep_after_corr = []
    for j, name in enumerate(cand_names):
        if const_frame.loc[j, "all_constant"]:
            corr_rows.append({"candidate": name, "max_abs_spearman_core": np.nan,
                              "correlated_with": "", "corr_rejected": True,
                              "reason": "near-constant on every corpus"})
            continue
        rhos = []
        for k in range(core_matrix.shape[1]):
            rho = spearmanr(Cmat[:, j], core_matrix[:, k], nan_policy="omit").statistic
            rhos.append(abs(float(rho)) if np.isfinite(rho) else 0.0)
        max_rho = max(rhos)
        worst = core[int(np.argmax(rhos))]
        rejected = max_rho >= CORR_LIMIT
        corr_rows.append({"candidate": name, "max_abs_spearman_core": max_rho,
                          "correlated_with": worst, "corr_rejected": rejected,
                          "reason": f"|rho|>={CORR_LIMIT}" if rejected else ""})
        if not rejected:
            keep_after_corr.append(j)

    # correlation among surviving candidates, keep first occurrence
    survivors = []
    for j in keep_after_corr:
        clash = None
        for k in survivors:
            rho = spearmanr(Cmat[:, j], Cmat[:, k], nan_policy="omit").statistic
            if np.isfinite(rho) and abs(float(rho)) >= CORR_LIMIT:
                clash = cand_names[k]
                break
        if clash is None:
            survivors.append(j)
        else:
            corr_rows[j] = {**corr_rows[j], "corr_rejected": True,
                            "correlated_with": clash,
                            "reason": f"|rho|>={CORR_LIMIT} with {clash}"}

    corr_frame = pd.DataFrame(corr_rows)
    print(f"candidates after constant/correlation filters: {len(survivors)}", flush=True)

    # ---- nested screening on CSIC ---------------------------------------
    outer = StratifiedKFold(n_splits=5, shuffle=True, random_state=C.SEED)
    deltas = {j: [] for j in survivors}
    core_scores = []

    for fold, (tr, _te) in enumerate(outer.split(X_all, y)):
        inner = StratifiedKFold(n_splits=INNER_SPLITS, shuffle=True, random_state=C.SEED + fold)
        inner_splits = list(inner.split(X_all[tr], y[tr]))

        def inner_f1(cols):
            scores = []
            for itr, iva in inner_splits:
                model = C.make_rf(n_estimators=N_TREES)
                model.fit(X_all[tr][itr][:, cols], y[tr][itr])
                pred = model.predict(X_all[tr][iva][:, cols])
                scores.append(f1_score(y[tr][iva], pred))
            return scores

        base = inner_f1(core_idx)
        core_scores.extend(base)
        for j in survivors:
            scores = inner_f1(core_idx + [cand_offset + j])
            deltas[j].append(float(np.mean(scores) - np.mean(base)))
        print(f"outer fold {fold}: screened {len(survivors)} candidates "
              f"({time.time() - started:.0f}s)", flush=True)

    screen_rows = []
    accepted = []
    for j in survivors:
        values = np.asarray(deltas[j], dtype=float)
        mean = float(values.mean())
        se = float(values.std(ddof=1) / np.sqrt(len(values))) if len(values) > 1 else float("inf")
        positive = int((values > 0).sum())
        ok = bool(mean > se and positive >= 4)
        if ok:
            accepted.append(cand_names[j])
        screen_rows.append({
            "candidate": cand_names[j],
            "mean_delta_f1": mean,
            "se_delta_f1": se,
            "positive_folds": positive,
            "accepted": ok,
        })

    screening = pd.DataFrame(screen_rows).sort_values("mean_delta_f1", ascending=False)
    screening.to_csv(OUT / "candidate_screening.csv", index=False)
    corr_frame.to_csv(OUT / "candidate_filters.csv", index=False)
    const_frame.to_csv(OUT / "candidate_constant.csv", index=False)

    # ---- descriptive univariate table -----------------------------------
    rows = []
    for j, name in enumerate(cand_names):
        col = Cmat[:, j]
        clean, attack = col[y == 0], col[y == 1]
        p = 1.0
        if np.std(col) > 0:
            p = float(mannwhitneyu(clean, attack, alternative="two-sided").pvalue)
        rows.append({
            "candidate": name,
            "clean_mean": float(clean.mean()),
            "attack_mean": float(attack.mean()),
            "clean_zero_frac": float(np.mean(clean == 0)),
            "attack_zero_frac": float(np.mean(attack == 0)),
            "p_value": p,
        })
    pd.DataFrame(rows).to_csv(OUT / "candidate_univariate.csv", index=False)

    v4_features = list(core) + accepted
    C.write_json(
        C.ARTIFACTS / "feature_selection" / "v4_definition.json",
        {
            "v3_features": names,
            "retained_core": core,
            "accepted_candidates": accepted,
            "rejected_candidates": [n for n in cand_names if n not in accepted],
            "v4_features": v4_features,
            "n_features": len(v4_features),
            "screening": {
                "outer_folds": 5,
                "inner_folds": INNER_SPLITS,
                "trees": N_TREES,
                "rule": "mean delta F1 > SE across outer folds and positive in >=4/5 folds",
            },
        },
    )
    print(screening.to_string(index=False))
    print(f"\naccepted: {accepted}")
    print(f"v4 size: {len(v4_features)}")


if __name__ == "__main__":
    main()
