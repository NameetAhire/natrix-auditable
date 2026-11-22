"""Measure the CPPP sidecar: promotion, rollback, and audit completeness.

The sidecar is started as a separate process with one fresh rule per cycle.
Each cycle runs the full protocol:

    validate(a), validate(b) -> canary start -> canary pass -> promote(policy)
    -> rollback (retire)

Client-side latency is measured around each HTTP call with
``time.perf_counter_ns``.  The sidecar fsyncs every audit record before it
replies, so the promotion and rollback numbers include durable audit writes,
not just in-memory state changes.

A second phase runs concurrent validations from many threads and then verifies
that the audit chain has no gaps, no duplicates, and no missing events.

Outputs
-------
experiments/results/cppp/cppp_bench.json
experiments/results/cppp/cppp_cycles.csv
experiments/results/cppp/audit.jsonl
"""

from __future__ import annotations

import argparse
import http.client
import json
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

OUT = C.RESULTS / "cppp"
OUT.mkdir(parents=True, exist_ok=True)
SCRIPT = Path(__file__).resolve().parent / "cppp_sidecar.py"
HOST = "127.0.0.1"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


class Client:
    def __init__(self, port: int) -> None:
        self.port = port
        self.local = threading.local()

    def _conn(self) -> http.client.HTTPConnection:
        conn = getattr(self.local, "conn", None)
        if conn is None:
            conn = http.client.HTTPConnection(HOST, self.port, timeout=10)
            self.local.conn = conn
        return conn

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[dict, float, float]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"} if payload else {}
        last: Exception | None = None
        for _ in range(2):
            try:
                conn = self._conn()
                started = time.perf_counter_ns()
                conn.request(method, path, body=payload, headers=headers)
                response = conn.getresponse()
                raw = response.read()
                elapsed = time.perf_counter_ns() - started
                data = json.loads(raw.decode("utf-8"))
                if response.status >= 400:
                    raise RuntimeError(f"{path}: {response.status} {data}")
                return data, elapsed, float(data.get("server_ns", 0))
            except Exception as exc:  # noqa: BLE001
                last = exc
                try:
                    self._conn().close()
                except Exception:
                    pass
                self.local.conn = None
        raise RuntimeError(f"{path} failed: {last}")


def percentile(values: list[float], p: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), p)) if values else 0.0


def summarise(values: list[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "p50_ms": percentile(values, 50) / 1e6,
        "p95_ms": percentile(values, 95) / 1e6,
        "p99_ms": percentile(values, 99) / 1e6,
        "mean_ms": float(np.mean(values) / 1e6) if values else 0.0,
        "max_ms": float(np.max(values) / 1e6) if values else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--parallel", type=int, default=32)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-fsync", action="store_true")
    args = parser.parse_args()

    cycles = max(1, args.cycles)
    parallel = max(1, args.parallel)
    port = args.port or free_port()
    rules = [f"c{i:04d}" for i in range(cycles)]
    par_rules = [f"p{i:04d}" for i in range(parallel)]
    audit_path = OUT / "audit.jsonl"
    if audit_path.exists():
        audit_path.unlink()

    cmd = [
        sys.executable, str(SCRIPT),
        "--host", HOST, "--port", str(port),
        "--agents", "agent-a,agent-b,agent-c,policy",
        "--policy-agent", "policy",
        "--rules", ",".join(rules + par_rules),
        "--quorum", "2", "--tau", "2", "--max-trust", "4",
        "--audit", str(audit_path),
    ]
    if args.no_fsync:
        cmd.append("--no-fsync")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    client = Client(port)

    # Wait for readiness.
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            client.call("GET", "/health")
            break
        except Exception:
            time.sleep(0.05)
    else:
        proc.kill()
        raise SystemExit(f"sidecar did not start:\n{proc.stdout.read() if proc.stdout else ''}")

    actions: dict[str, list[float]] = {k: [] for k in
        ("validate", "canary_start", "canary_observe", "canary_pass", "promote", "retire", "tick")}
    cycles_rows: list[dict] = []

    for rule in rules:
        t_cycle = time.perf_counter_ns()
        data, ns, _ = client.call("POST", "/validate", {"agent": "agent-a", "rule": rule})
        actions["validate"].append(ns)
        data, ns, _ = client.call("POST", "/validate", {"agent": "agent-b", "rule": rule})
        actions["validate"].append(ns)

        data, ns, _ = client.call("POST", "/canary/start", {"rule": rule})
        actions["canary_start"].append(ns)
        if data["state"]["rules"][rule]["state"] != "canary":
            raise SystemExit(f"canary did not start for {rule}")

        for _ in range(2):
            data, ns, _ = client.call("POST", "/canary/observe", {"rule": rule, "hit": False})
            actions["canary_observe"].append(ns)

        data, ns, _ = client.call("POST", "/canary/pass", {"rule": rule})
        actions["canary_pass"].append(ns)

        t_promote = time.perf_counter_ns()
        data, ns, server_ns = client.call("POST", "/promote", {"agent": "policy", "rule": rule})
        promote_done = time.perf_counter_ns()
        actions["promote"].append(ns)
        if rule not in data["state"]["active"]:
            raise SystemExit(f"promotion not active for {rule}")

        t_rollback = time.perf_counter_ns()
        data, ns, _ = client.call("POST", "/retire", {"rule": rule, "reason": "benchmark"})
        rollback_done = time.perf_counter_ns()
        actions["retire"].append(ns)
        if rule in data["state"]["active"]:
            raise SystemExit(f"rollback did not remove {rule}")

        cycles_rows.append({
            "rule": rule,
            "cycle_ms": (promote_done - t_cycle) / 1e6,
            "promote_ms": (promote_done - t_promote) / 1e6,
            "rollback_ms": (rollback_done - t_rollback) / 1e6,
            "promote_server_ms": server_ns / 1e6,
        })

    # Concurrent validations: two agents per rule, all rules at once.
    def validate_pair(rule: str) -> tuple[float, float]:
        local = Client(port)
        _, ns_a, _ = local.call("POST", "/validate", {"agent": "agent-a", "rule": rule})
        _, ns_b, _ = local.call("POST", "/validate", {"agent": "agent-b", "rule": rule})
        return ns_a, ns_b

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        concurrent = list(pool.map(validate_pair, par_rules))
    concurrent_s = time.perf_counter() - started
    for ns_a, ns_b in concurrent:
        actions["validate"].extend([ns_a, ns_b])

    # Tick path (also exercises auto-retire bookkeeping).
    for rule in par_rules[: min(parallel, 8)]:
        client.call("POST", "/canary/start", {"rule": rule})
        for _ in range(2):
            client.call("POST", "/canary/observe", {"rule": rule, "hit": False})
        client.call("POST", "/canary/pass", {"rule": rule})
        client.call("POST", "/promote", {"agent": "policy", "rule": rule})
    for _ in range(4):
        data, ns, _ = client.call("POST", "/tick", {})
        actions["tick"].append(ns)
    auto_retired = sum(
        1 for rule in par_rules[: min(parallel, 8)]
        if data["state"]["rules"][rule]["state"] == "retired"
    )

    verification, _, _ = client.call("GET", "/audit/verify")
    final, _, _ = client.call("GET", "/state")
    audit, _, _ = client.call("GET", "/audit")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    counts = audit["audit"]["counts"]
    expected = {
        "validate": 2 * cycles + 2 * parallel,
        "start_canary": cycles + min(parallel, 8),
        "observe_canary": 2 * (cycles + min(parallel, 8)),
        "pass_canary": cycles + min(parallel, 8),
        "promote": cycles + min(parallel, 8),
        "retire": cycles,
        "tick": 4,
    }
    count_errors = {
        key: {"expected": value, "actual": counts.get(key, 0)}
        for key, value in expected.items() if counts.get(key, 0) != value
    }
    # Every promotion must have exactly one retirement, manual or automatic.
    promotions = counts.get("promote", 0)
    retirements = counts.get("retire", 0) + counts.get("auto_retire", 0)
    completeness = {
        "chain_ok": bool(verification["verification"]["chain_ok"]),
        "records": verification["verification"]["records"],
        "seq_expected": audit["audit"]["seq"],
        "count_errors": count_errors,
        "promotions": promotions,
        "retirements": retirements,
        "every_promotion_retired": promotions == retirements,
        "auto_retired": auto_retired,
        "no_active_below_tau": all(
            rs["trust"] >= 2 for rs in final["state"]["rules"].values()
            if rs["state"] == "promoted"
        ),
        "invariants": final["state"]["invariants"],
    }

    import pandas as pd
    pd.DataFrame(cycles_rows).to_csv(OUT / "cppp_cycles.csv", index=False)
    result = {
        "sidecar": {
            "host": HOST, "port": port, "fsync": not args.no_fsync,
            "quorum": 2, "tau": 2, "max_trust": 4,
            "canary_obs": 2,
            "agents": ["agent-a", "agent-b", "agent-c", "policy"],
        },
        "cycles": cycles,
        "parallel_rules": parallel,
        "concurrent_validation_seconds": concurrent_s,
        "latency": {k: summarise(v) for k, v in actions.items()},
        "cycle_latency": summarise([r["cycle_ms"] * 1e6 for r in cycles_rows]),
        "completeness": completeness,
        "audit_head": audit["audit"]["head"],
        "audit_path": str(audit_path),
    }
    C.write_json(OUT / "cppp_bench.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
