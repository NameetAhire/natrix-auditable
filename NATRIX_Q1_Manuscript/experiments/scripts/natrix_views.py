"""What does NATRIX actually see?  Full-request vs path vs payload views.

The manuscript's earlier wording called v3 a "payload contract".  The runtime
actually passes ``path?query body`` plus the method and User-Agent.  On SR-BH
the lexical payload-only view collapses to 10.91% recall while NATRIX reaches
87.83%, which is only consistent if NATRIX is using the path or other request
metadata.  This script measures that directly by retraining the same forest on
the same rows and folds under five input views:

    full       path?query body          (the shipped contract)
    no_path    ?query body              (path removed)
    path_only  path                     (query and body removed)
    query_only ?query                   (path and body removed)
    body_only  body                     (path and query removed)

Method and User-Agent are held constant in every view, so the difference is
attributable to the request text, not to a changed metadata contract.

Outputs
-------
experiments/results/baselines/natrix_views_srbh20k.json
experiments/results/baselines/natrix_views_srbh20k.csv
experiments/results/baselines/natrix_view_{view}_oof.npz
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)

VIEWS = ["full", "no_path", "path_only", "query_only", "body_only"]


def payload_for(row, view: str) -> str:
    path = str(row.path or "")
    query = str(row.query or "")
    body = str(row.body or "")
    if view == "full":
        return path + (("?" + query) if query else "") + ((" " + body) if body else "")
    if view == "no_path":
        return ("?" + query if query else "") + ((" " + body) if body else "")
    if view == "path_only":
        return path
    if view == "query_only":
        return "?" + query if query else ""
    if view == "body_only":
        return " " + body if body else ""
    raise ValueError(view)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["srbh20k", "csic"], default="srbh20k")
    parser.add_argument("--protocol", choices=["P1", "P2"], default="P1")
    args = parser.parse_args()

    if args.corpus == "srbh20k":
        frame = pd.read_parquet(
            OUT / "srbh_sample20k_requests.parquet",
            columns=["method", "path", "query", "body", "user_agent", "label"],
        )
        if args.protocol == "P1":
            z = np.load(OUT / "natrix_srbh_sample20k_oof.npz", allow_pickle=True)
            folds = [(np.setdiff1d(np.arange(len(frame)), np.asarray(te, dtype=int)), np.asarray(te, dtype=int)) for te in z["folds"]]
        else:
            z = np.load(OUT / "srbh20k_P2_folds_seed42.npz", allow_pickle=True)
            folds = [(z[f"tr_{i}"], z[f"te_{i}"]) for i in range(5)]
        tag = "srbh20k"
    else:
        records, _ = C.csic_unique()
        frame = pd.DataFrame(
            [
                {
                    "method": r.method,
                    "path": r.path,
                    "query": r.query,
                    "body": r.body,
                    "user_agent": r.user_agent,
                    "label": int(r.label),
                }
                for r in records
            ]
        )
        f = np.load(C.RESULTS / "corpora" / f"csic_{args.protocol}_folds_seed42.npz", allow_pickle=True)
        folds = [(f[f"tr_{i}"], f[f"te_{i}"]) for i in range(5)]
        tag = "csic"

    y = frame.label.to_numpy(dtype=int)
    rows = []
    for view in VIEWS:
        records = [
            C.make_request(
                rid=str(i),
                source=tag,
                label=int(row.label),
                method=row.method,
                target=row.path + (("?" + row.query) if row.query else ""),
                body=row.body,
                user_agent=row.user_agent,
            )
            for i, row in enumerate(frame.itertuples(index=False))
        ]
        # Replace only the payload string; method/UA are unchanged.
        for rec, row in zip(records, frame.itertuples(index=False)):
            rec.payload = payload_for(row, view)

        X, _ = C.extract_matrix(records, dtype=np.float32)
        proba = np.zeros(len(y), dtype=np.float32)
        for k, (tr, te) in enumerate(folds):
            model = C.make_rf(random_state=C.SEED)
            model.fit(X[tr], y[tr])
            proba[te] = model.predict_proba(X[te])[:, 1]
            print(f"  {view} fold {k}", flush=True)

        pred_fpr2 = np.zeros(len(y), dtype=int)
        thresholds = []
        for tr, te in folds:
            t = best_threshold(proba[tr], y[tr], fpr_cap=0.02)
            pred_fpr2[te] = (proba[te] >= t).astype(int)
            thresholds.append(float(t))
        m = metrics_from_pred(y, pred_fpr2)
        m.update(
            {
                "corpus": tag,
                "view": view,
                "n": int(len(y)),
                "threshold_mean": float(np.mean(thresholds)),
                "thresholds": ";".join(f"{t:.2f}" for t in thresholds),
            }
        )
        rows.append(m)
        np.savez(OUT / f"natrix_view_{tag}_{args.protocol}_{view}_oof.npz", proba=proba, y=y,
                 folds=np.asarray([te for _, te in folds], dtype=object))
        print(
            f"{tag} {args.protocol} {view}: acc={m['accuracy']:.4f} fpr={m['fpr']:.4f} "
            f"recall={m['recall']:.4f} f1={m['f1']:.4f}",
            flush=True,
        )

    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"natrix_views_{tag}_{args.protocol}.csv", index=False)
    C.write_json(OUT / f"natrix_views_{tag}_{args.protocol}.json", out.to_dict("records"))
    print(out[["view", "accuracy", "fpr", "recall", "f1"]].to_string(index=False))


if __name__ == "__main__":
    main()
