"""Cross-corpus transfer and real-world FPR.

Sources: CSIC 2010 and SR-BH 2020.
Targets: ECML/PKDD 2007, SR-BH 2020, CSIC 2010, OpenAppSec WCP.

The decision threshold is selected on *source* out-of-fold predictions only;
the target corpus is never used for threshold selection.  OpenAppSec
legitimate traffic is never used for training or model selection.

Outputs
-------
experiments/results/transfer/transfer_metrics.csv
experiments/results/transfer/wcp_family_recall.csv
experiments/results/transfer/transfer_summary.json
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "transfer"
OUT.mkdir(parents=True, exist_ok=True)


def load_source(name):
    if name == "csic":
        records, _ = C.csic_unique()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        return X, C.label_array(records)
    if name == "srbh":
        z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
        return z["X"], z["y"]
    raise ValueError(name)


def load_target(name):
    if name == "ecml":
        records = C.load_ecml_records()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        return X, C.label_array(records), None
    if name == "srbh":
        z = np.load(C.PROCESSED / "srbh" / "srbh_features.npz", allow_pickle=True)
        return z["X"], z["y"], None
    if name == "csic":
        records, _ = C.csic_unique()
        X, _ = C.extract_matrix(records, dtype=np.float32)
        return X, C.label_array(records), None
    if name == "wcp":
        z = np.load(C.PROCESSED / "openappsec" / "wcp_features.npz", allow_pickle=True)
        return z["X"], z["y"], z["families"]
    raise ValueError(name)


def source_threshold(X, y, seed=C.SEED, source: str | None = None) -> dict:
    """Two source-only operating points: F1-optimal and FPR <= 2%.

    If the corpus evaluation has already saved 5-fold OOF probabilities for the
    same seed and splitter, those are reused: refitting the identical folds
    would produce the same numbers.  The fallback recomputes them.
    """
    oof_path = C.RESULTS / "corpora" / f"{source}_P1_oof.npz" if source else None
    if oof_path is not None and oof_path.exists():
        z = np.load(oof_path)
        oof = z["proba"].astype(float)
        if len(oof) != len(y) or not np.array_equal(z["y"], y):
            raise ValueError(f"cached OOF does not match source {source}")
        print(f"source {source}: reusing cached P1 OOF {oof_path.name}", flush=True)
    else:
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        oof = np.zeros(len(y), dtype=float)
        for tr, te in skf.split(X, y):
            model = C.make_rf()
            model.fit(X[tr], y[tr])
            oof[te] = model.predict_proba(X[te])[:, 1]
    from sklearn.metrics import confusion_matrix as cm
    from sklearn.metrics import f1_score

    best = {"f1": (0.5, -1.0), "fpr2": (0.99, -1.0)}
    for t in np.round(np.arange(0.01, 1.0, 0.01), 2):
        pred = (oof >= t).astype(int)
        tn, fp, fn, tp = cm(y, pred, labels=[0, 1]).ravel()
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        score = f1_score(y, pred, zero_division=0)
        if score > best["f1"][1]:
            best["f1"] = (float(t), float(score))
        if fpr <= 0.02 and score > best["fpr2"][1]:
            best["fpr2"] = (float(t), float(score))
    return {policy: {"threshold": value[0], "oof_f1": value[1]}
            for policy, value in best.items()}


def metrics(y, pred, proba) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    out = {
        "accuracy": float((tp + tn) / len(y)),
        "fpr": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "fnr": float(fn / (fn + tp)) if (fn + tp) else 0.0,
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
        "n": int(len(y)),
    }
    if len(np.unique(y)) > 1:
        out["roc_auc"] = float(roc_auc_score(y, proba))
    else:
        out["roc_auc"] = float("nan")
    return out


def main() -> None:
    started = time.time()
    sources = {}
    for name in ("csic", "srbh"):
        sources[name] = load_source(name)
        print(f"source {name}: {sources[name][0].shape}", flush=True)

    rows = []
    family_rows = []

    for source_name, (Xs, ys) in sources.items():
        thresholds = source_threshold(Xs, ys, source=source_name)
        model = C.make_rf()
        model.fit(Xs, ys)
        print(f"source {source_name}: thresholds="
              f"{ {k: round(v['threshold'], 2) for k, v in thresholds.items()} } "
              f"({time.time() - started:.0f}s)", flush=True)

        for target_name in ("csic", "ecml", "srbh", "wcp"):
            if source_name == target_name:
                continue
            Xt, yt, families = load_target(target_name)
            proba = model.predict_proba(Xt)[:, 1]
            for policy, info in thresholds.items():
                threshold = info["threshold"]
                pred = (proba >= threshold).astype(int)
                m = metrics(yt, pred, proba)
                m.update({"source": source_name, "target": target_name,
                          "policy": policy, "threshold": threshold,
                          "threshold_source": "source OOF, " +
                          ("F1-optimal" if policy == "f1" else "FPR<=2%")})
                rows.append(m)

                if families is not None:
                    for family in sorted(set(families)):
                        mask = families == family
                        fam_labels = yt[mask]
                        fam_pred = pred[mask]
                        tn, fp, fn, tp = confusion_matrix(
                            fam_labels, fam_pred, labels=[0, 1]
                        ).ravel()
                        family_rows.append({
                            "source": source_name,
                            "policy": policy,
                            "family": str(family),
                            "n": int(mask.sum()),
                            "recall_or_specificity": float(
                                tp / (tp + fn) if (tp + fn) else (tn / (tn + fp))
                            ),
                            "fpr": float(fp / (fp + tn)) if (fp + tn) else 0.0,
                        })
                print(f"  {source_name} -> {target_name} [{policy}]: "
                      f"acc={m['accuracy']:.4f} fpr={m['fpr']:.4f} "
                      f"fnr={m['fnr']:.4f}", flush=True)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "transfer_metrics.csv", index=False)
    pd.DataFrame(family_rows).to_csv(OUT / "wcp_family_recall.csv", index=False)
    C.write_json(OUT / "transfer_summary.json", {
        "threshold_policy": "source out-of-fold only; F1-optimal and FPR<=2%",
        "results": frame.to_dict("records"),
        "wcp": [r for r in rows if r["target"] == "wcp"],
    })
    print(frame[["source", "target", "policy", "threshold", "accuracy",
                  "fpr", "fnr", "f1"]].to_string(index=False))


if __name__ == "__main__":
    main()
