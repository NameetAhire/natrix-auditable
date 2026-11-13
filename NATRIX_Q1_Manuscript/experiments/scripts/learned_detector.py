"""Independent learned detector: a small character-level CNN.

This is a deliberately simple, self-contained learned baseline, not a
reproduction of a named system.  It sees the same text views as the lexical
baseline (full = path+query+body, payload = query+body), is trained on the same
folds, and is calibrated with the same leave-one-fold-out FPR <= 2% policy.

Outputs
-------
experiments/results/baselines/learned_{corpus}_{protocol}_{view}.json
experiments/results/baselines/learned_{corpus}_{protocol}_{view}_oof.npz
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from compare_v3_v4 import best_threshold, metrics_from_pred  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)
MAX_LEN = 512
VOCAB = 256
SEED = 42


class CharCNN(nn.Module):
    def __init__(self, dim: int = 32, channels: int = 64):
        super().__init__()
        self.emb = nn.Embedding(VOCAB, dim, padding_idx=0)
        self.conv1 = nn.Conv1d(dim, channels, 3, padding=1)
        self.conv2 = nn.Conv1d(channels, channels, 5, padding=2)
        self.drop = nn.Dropout(0.2)
        self.fc = nn.Linear(channels, 1)

    def forward(self, x):
        h = self.emb(x).transpose(1, 2)
        h = F.relu(self.conv1(h))
        h = F.relu(self.conv2(h))
        h = h.max(dim=2).values
        return self.fc(self.drop(h)).squeeze(1)


def encode(texts) -> np.ndarray:
    out = np.zeros((len(texts), MAX_LEN), dtype=np.int64)
    for i, text in enumerate(texts):
        raw = str(text).encode("utf-8", errors="ignore")[:MAX_LEN]
        out[i, : len(raw)] = np.frombuffer(raw, dtype=np.uint8)
    return out


def text_of(row, view: str) -> str:
    if view == "payload":
        return f"{row.query} {row.body}"
    return f"{row.path} {row.query} {row.body}"


def load_corpus(corpus: str, protocol: str):
    if corpus == "csic":
        records, _ = C.csic_unique()
        rows = pd.DataFrame(
            [
                {
                    "method": r.method, "path": r.path, "query": r.query,
                    "body": r.body, "user_agent": r.user_agent,
                    "label": int(r.label),
                }
                for r in records
            ]
        )
    elif corpus == "ecml":
        records = C.load_ecml_records()
        rows = pd.DataFrame(
            [
                {
                    "method": r.method, "path": r.path, "query": r.query,
                    "body": r.body, "user_agent": r.user_agent,
                    "label": int(r.label),
                }
                for r in records
            ]
        )
    elif corpus == "srbh20k":
        rows = pd.read_parquet(
            OUT / "srbh_sample20k_requests.parquet",
            columns=["method", "path", "query", "body", "user_agent", "label"],
        )
    else:
        raise ValueError(corpus)

    y = rows.label.to_numpy(dtype=int)
    if protocol == "P1":
        folds = list(
            StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(rows, y)
        )
    else:
        fold_path = {
            "csic": C.RESULTS / "corpora" / "csic_P2_folds_seed42.npz",
            "ecml": C.RESULTS / "corpora" / "ecml_P2_folds_seed42.npz",
            "srbh20k": OUT / "srbh20k_P2_folds_seed42.npz",
        }[corpus]
        z = np.load(fold_path, allow_pickle=True)
        folds = [(z[f"tr_{i}"], z[f"te_{i}"]) for i in range(5)]
    return rows, y, folds


def train_fold(X, y, tr, te, fold: int):
    torch.manual_seed(SEED + fold)
    np.random.seed(SEED + fold)
    model = CharCNN()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    loss_fn = nn.BCEWithLogitsLoss()

    x_tr = torch.from_numpy(X[tr])
    y_tr = torch.from_numpy(y[tr].astype(np.float32))
    x_te = torch.from_numpy(X[te])
    n = len(tr)
    batch = 256
    model.train()
    for epoch in range(5):
        order = np.random.permutation(n)
        total = 0.0
        for start in range(0, n, batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            logits = model(x_tr[idx])
            loss = loss_fn(logits, y_tr[idx])
            loss.backward()
            opt.step()
            total += float(loss) * len(idx)
        print(f"    fold {fold} epoch {epoch}: loss={total / n:.4f}", flush=True)

    model.eval()
    with torch.no_grad():
        proba = torch.sigmoid(model(x_te)).numpy().astype(np.float32)
    return proba


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh20k"], required=True)
    parser.add_argument("--protocol", choices=["P1", "P2"], required=True)
    parser.add_argument("--views", nargs="+", default=["full", "payload"])
    args = parser.parse_args()

    torch.set_num_threads(4)
    rows, y, folds = load_corpus(args.corpus, args.protocol)
    print(f"{args.corpus} {args.protocol}: n={len(y):,}", flush=True)

    for view in args.views:
        started = time.time()
        texts = [text_of(row, view) for row in rows.itertuples(index=False)]
        X = encode(texts)
        proba = np.zeros(len(y), dtype=np.float32)
        for k, (tr, te) in enumerate(folds):
            proba[te] = train_fold(X, y, tr, te, k)
            print(f"  {args.corpus}/{args.protocol}/{view} fold {k}: "
                  f"{time.time() - started:.0f}s", flush=True)

        pred = np.zeros(len(y), dtype=int)
        thresholds = []
        for tr, te in folds:
            t = best_threshold(proba[tr], y[tr], fpr_cap=0.02)
            pred[te] = (proba[te] >= t).astype(int)
            thresholds.append(float(t))

        result = {
            "corpus": args.corpus,
            "protocol": args.protocol,
            "view": view,
            "learner": "char-CNN (emb32, conv64 k3+k5, max-pool, 5 epochs)",
            "elapsed_seconds": round(time.time() - started, 1),
            "n": int(len(y)),
            "auc": float(roc_auc_score(y, proba)),
            "fpr2_crossfit": {
                **metrics_from_pred(y, pred),
                "threshold_mean": float(np.mean(thresholds)),
                "thresholds": thresholds,
            },
        }
        C.write_json(OUT / f"learned_{args.corpus}_{args.protocol}_{view}.json", result)
        np.savez(
            OUT / f"learned_{args.corpus}_{args.protocol}_{view}_oof.npz",
            proba=proba, y=y,
            folds=np.asarray([te for _, te in folds], dtype=object),
        )
        print(json.dumps(result["fpr2_crossfit"], indent=2), flush=True)


if __name__ == "__main__":
    main()
