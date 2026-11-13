"""Evaluate OWASP ModSecurity CRS as a baseline on the NATRIX corpora.

The proxy is the official ``owasp/modsecurity-crs`` nginx image, default
paranoia level 1, inbound anomaly threshold 5.  The origin returns 200 for
every request, so a 403 is the WAF's decision.  Requests are replayed as HTTP,
not scored from extracted features, which is the point of the comparison.

The harness is deliberately independent of NATRIX: it loads the same
deduplicated records and computes the same confusion-matrix metrics, but it
never calls the NATRIX model or feature registry.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "baselines"
OUT.mkdir(parents=True, exist_ok=True)

HOST = "127.0.0.1"
PORT = 8088
HOST_HEADER = "test-site.com"

# A literal '%' that is not a valid escape (for example the IIS '%uXXXX'
# convention) makes nginx reject the request line with 400 before ModSecurity
# sees it.  Encode only those, and preserve valid escapes so that the WAF
# receives the same encoding the corpus recorded.
_INVALID_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _wire_target(path: str, query: str) -> str:
    target = path or "/"
    if query:
        target += "?" + query
    target = _INVALID_PERCENT.sub("%25", target)
    # Preserve existing escapes and reserved delimiters; encode only characters
    # that cannot appear on an HTTP request line.  CRS decodes the result.
    return urllib.parse.quote(
        target,
        safe="/%?&=:;+$,@!~*'()[]{}|\\^`<>#-._",
    )


class Client:
    def __init__(self) -> None:
        self.conn: http.client.HTTPConnection | None = None
        self.lock = threading.Lock()

    def _connect(self) -> http.client.HTTPConnection:
        conn = http.client.HTTPConnection(HOST, PORT, timeout=15)
        conn.connect()
        return conn

    def send(self, rec: dict) -> tuple[int, float, str]:
        method = (rec.get("method") or "GET").upper()
        path = rec.get("path") or "/"
        query = rec.get("query") or ""
        body = (rec.get("body") or "").encode("utf-8", "replace")
        ua = rec.get("user_agent") or "Mozilla/5.0"
        content_type = rec.get("content_type") or (
            "application/json" if body[:1] in (b"{", b"[") else "application/x-www-form-urlencoded"
        )
        target = _wire_target(path, query)

        headers = {
            "Host": rec.get("host") or HOST_HEADER,
            "User-Agent": ua,
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        if body:
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(body))

        last_exc = None
        for attempt in range(2):
            try:
                if self.conn is None:
                    self.conn = self._connect()
                started = time.perf_counter()
                self.conn.putrequest(method, target, skip_host=True, skip_accept_encoding=True)
                for key, value in headers.items():
                    self.conn.putheader(key, value)
                self.conn.endheaders()
                if body:
                    self.conn.send(body)
                response = self.conn.getresponse()
                response.read()
                status = int(response.status)
                elapsed = (time.perf_counter() - started) * 1000.0
                if response.will_close:
                    self.conn.close()
                    self.conn = None
                return status, elapsed, ""
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if self.conn is not None:
                    try:
                        self.conn.close()
                    except Exception:
                        pass
                self.conn = None
                time.sleep(0.05 * (attempt + 1))
        return 0, 0.0, str(last_exc)


def load_records(corpus: str, limit: int | None, seed: int = 42) -> pd.DataFrame:
    if corpus == "csic":
        records, _ = C.csic_unique()
        rows = [
            {
                "method": r.method, "path": r.path, "query": r.query,
                "body": r.body, "user_agent": r.user_agent, "label": int(r.label),
                "family": r.declared_class or "anomalous",
            }
            for r in records
        ]
    elif corpus == "ecml":
        records = C.load_ecml_records()
        rows = [
            {
                "method": r.method, "path": r.path, "query": r.query,
                "body": r.body, "user_agent": r.user_agent, "label": int(r.label),
                "family": r.declared_class or "Valid",
            }
            for r in records
        ]
    elif corpus == "srbh":
        path = C.PROCESSED / "srbh" / "srbh_requests.parquet"
        if not path.exists():
            raise SystemExit(f"missing {path}; run build_srbh_requests.py")
        frame = pd.read_parquet(path)
        frame = frame[["method", "path", "query", "body", "user_agent", "label", "family"]]
        rows = frame.to_dict("records")
    elif corpus == "wcp":
        # Reuse the shared 20k sample so CRS, NATRIX, and the lexical baseline
        # score exactly the same rows in exactly the same order.
        path = OUT / "wcp_sample20k_requests.parquet"
        if not path.exists():
            raise SystemExit(f"missing {path}; run evaluate_wcp_sample.py")
        frame = pd.read_parquet(
            path,
            columns=["method", "path", "query", "body", "user_agent", "label", "family"],
        )
        rows = frame.to_dict("records")
        limit = None
    else:
        raise SystemExit(f"unknown corpus {corpus}")

    frame = pd.DataFrame.from_records(rows)
    if limit is not None and limit < len(frame):
        # Keep the class ratio while bounding replay time.
        parts = []
        for label, group in frame.groupby("label", sort=True):
            take = max(1, int(round(limit * len(group) / len(frame))))
            parts.append(group.sample(n=min(take, len(group)), random_state=seed))
        frame = pd.concat(parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return frame


def metrics(y: np.ndarray, blocked: np.ndarray) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, blocked, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "accuracy": float((tp + tn) / len(y)),
        "fpr": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "fnr": float(fn / (fn + tp)) if (fn + tp) else 0.0,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
        "n": int(len(y)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", choices=["csic", "ecml", "srbh", "wcp"], required=True)
    parser.add_argument("--limit", type=int, default=None,
                        help="stratified sample size; default is the whole corpus")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--tag", type=str, default="crs_pl1")
    parser.add_argument("--port", type=int, default=8088,
                        help="host port of the CRS reverse proxy")
    parser.add_argument("--paranoia-level", type=int, default=1,
                        help="CRS blocking paranoia level (1, 2, 3, or 4)")
    parser.add_argument("--anomaly-inbound", type=int, default=5)
    args = parser.parse_args()

    global PORT
    PORT = args.port
    started = time.time()
    frame = load_records(args.corpus, args.limit)
    print(f"{args.corpus}: {len(frame):,} requests, "
          f"labels={frame.label.value_counts().to_dict()}", flush=True)

    local = threading.local()

    def work(item):
        idx, rec = item
        if not hasattr(local, "client"):
            local.client = Client()
        status, elapsed, error = local.client.send(rec)
        return idx, status, elapsed, error

    results = [None] * len(frame)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(work, (i, rec)) for i, rec in enumerate(frame.to_dict("records"))]
        done = 0
        for fut in as_completed(futures):
            idx, status, elapsed, error = fut.result()
            results[idx] = (status, elapsed, error)
            done += 1
            if done % 2000 == 0:
                rate = done / max(time.time() - started, 1e-9)
                print(f"  {done:,}/{len(frame):,}  {rate:,.0f} req/s  "
                      f"{time.time() - started:,.0f}s", flush=True)

    status = np.asarray([r[0] for r in results], dtype=int)
    latency = np.asarray([r[1] for r in results], dtype=float)
    errors = np.asarray([r[2] for r in results], dtype=object)
    y = frame.label.to_numpy(dtype=int)
    blocked = (status == 403).astype(int)

    result = {
        "corpus": args.corpus,
        "engine": "ModSecurity CRS 4.25.2 (nginx image)",
        "paranoia_level": args.paranoia_level,
        "anomaly_inbound": args.anomaly_inbound,
        "limit": args.limit,
        "workers": args.workers,
        "elapsed_seconds": round(time.time() - started, 1),
        "throughput_rps": round(len(frame) / max(time.time() - started, 1e-9), 1),
        "status_counts": {str(k): int(v) for k, v in zip(*np.unique(status, return_counts=True))},
        "errors": int((status == 0).sum()),
        **metrics(y, blocked),
        "latency_ms": {
            "p50": float(np.percentile(latency[latency > 0], 50)) if (latency > 0).any() else None,
            "p95": float(np.percentile(latency[latency > 0], 95)) if (latency > 0).any() else None,
            "p99": float(np.percentile(latency[latency > 0], 99)) if (latency > 0).any() else None,
        },
    }

    detail = frame.copy()
    detail["status"] = status
    detail["blocked"] = blocked
    detail["latency_ms"] = latency
    detail["error"] = errors
    detail.to_parquet(OUT / f"{args.tag}_{args.corpus}_requests.parquet", index=False)
    C.write_json(OUT / f"{args.tag}_{args.corpus}.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
