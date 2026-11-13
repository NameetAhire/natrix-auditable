"""CPPP sidecar: the executable promotion protocol behind an HTTP boundary.

The TLA+ model in ``artifacts/formal/Cppp.tla`` and the reference class in
``artifacts/formal/cppp.py`` describe the transition relation.  This module
puts the same relation behind a small HTTP service so that promotion and
rollback can be *measured* rather than only model-checked.  It does not modify
the shipped proxy: it is a sidecar that a deployment could call before
activating a policy artifact.

Design rules
------------
* One process, one policy agent, one lock.  Every transition is serialised, so
  the audit order is a total order.
* Every accepted transition is appended to a hash-chained audit log and
  fsync'ed before the response is sent.  A crash can therefore lose at most the
  in-flight request, never an acknowledged transition.
* The HTTP layer is deliberately thin: it parses JSON, calls the protocol,
  writes the audit record, and returns the snapshot.  The protocol itself is
  the same guard structure as the TLA+ model.

Endpoints
---------
GET  /health
GET  /state
GET  /audit
GET  /audit/verify
POST /validate        {"agent": "...", "rule": "..."}
POST /canary/start    {"rule": "..."}
POST /canary/pass     {"rule": "..."}
POST /promote         {"agent": "...", "rule": "..."}
POST /retire          {"rule": "..."}          # rollback
POST /reject          {"rule": "..."}
POST /tick            {}

Run:
    python experiments/scripts/cppp_sidecar.py --port 8099 \
        --audit experiments/results/cppp/audit.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


class ProtocolError(RuntimeError):
    pass


class Rule:
    __slots__ = ("state", "votes", "trust", "canary_passed", "promoted_tick", "retired_tick")

    def __init__(self) -> None:
        self.state = "observed"
        self.votes: set[str] = set()
        self.trust = 0
        self.canary_passed = False
        self.promoted_tick: int | None = None
        self.retired_tick: int | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "votes": sorted(self.votes),
            "trust": self.trust,
            "canary_passed": self.canary_passed,
            "promoted_tick": self.promoted_tick,
            "retired_tick": self.retired_tick,
        }


class Sidecar:
    """Thread-safe CPPP implementation with a durable hash-chained audit log."""

    def __init__(
        self,
        agents: list[str],
        policy_agent: str,
        rules: list[str],
        quorum: int,
        tau: int,
        max_trust: int,
        audit_path: Path,
        fsync: bool = True,
    ) -> None:
        if policy_agent not in agents:
            raise ValueError("policy agent must be one of the agents")
        if not (1 <= quorum <= len(agents)):
            raise ValueError("quorum must be in [1, len(agents)]")
        if not (0 <= tau <= max_trust):
            raise ValueError("tau must be in [0, max_trust]")
        self.agents = frozenset(agents)
        self.policy_agent = policy_agent
        self.quorum = quorum
        self.tau = tau
        self.max_trust = max_trust
        self.rules = {name: Rule() for name in rules}
        self.audited: set[str] = set()
        self.tick_no = 0
        self.lock = threading.RLock()
        self.fsync = fsync
        self.audit_path = audit_path
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self._prev = GENESIS
        self._records: list[dict[str, Any]] = []
        self._counts: dict[str, int] = {}
        self._reset_log()

    # -- audit -----------------------------------------------------------
    def _reset_log(self) -> None:
        with open(self.audit_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("")

    def _canonical(self, record: dict[str, Any]) -> bytes:
        return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _append(self, action: str, rule: str | None, agent: str | None, detail: str = "") -> None:
        record: dict[str, Any] = {
            "seq": self._seq,
            "ts": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "monotonic_ns": time.monotonic_ns(),
            "action": action,
            "rule": rule,
            "agent": agent,
            "detail": detail,
            "prev": self._prev,
        }
        digest = hashlib.sha256(self._prev.encode("ascii") + self._canonical(record)).hexdigest()
        record["hash"] = digest
        line = self._canonical(record) + b"\n"
        with open(self.audit_path, "ab") as handle:
            handle.write(line)
            handle.flush()
            if self.fsync:
                os.fsync(handle.fileno())
        self._prev = digest
        self._seq += 1
        self._records.append(record)
        self._counts[action] = self._counts.get(action, 0) + 1

    # -- guards ----------------------------------------------------------
    def _rule(self, name: str) -> Rule:
        try:
            return self.rules[name]
        except KeyError:
            raise ProtocolError(f"unknown rule {name!r}") from None

    def _require_agent(self, agent: str) -> None:
        if agent not in self.agents:
            raise ProtocolError(f"unknown agent {agent!r}")

    def _quorum_ok(self, rs: Rule) -> bool:
        return len(rs.votes) >= self.quorum

    def _trust_ok(self, rs: Rule) -> bool:
        return rs.trust >= self.tau

    # -- transitions -----------------------------------------------------
    def validate(self, agent: str, rule: str) -> dict[str, Any]:
        with self.lock:
            rs = self._rule(rule)
            self._require_agent(agent)
            if rs.state not in ("observed", "canary"):
                raise ProtocolError(f"cannot validate a rule in state {rs.state}")
            rs.votes.add(agent)
            rs.trust = min(self.max_trust, rs.trust + 1)
            self._append("validate", rule, agent)
            return self.snapshot_locked()

    def start_canary(self, rule: str, agent: str | None = None) -> dict[str, Any]:
        with self.lock:
            rs = self._rule(rule)
            if rs.state != "observed":
                raise ProtocolError("canary may only start from observed")
            if not self._quorum_ok(rs):
                raise ProtocolError("quorum not reached")
            if not self._trust_ok(rs):
                raise ProtocolError("trust below tau")
            rs.state = "canary"
            self._append("start_canary", rule, agent)
            return self.snapshot_locked()

    def pass_canary(self, rule: str, agent: str | None = None) -> dict[str, Any]:
        with self.lock:
            rs = self._rule(rule)
            if rs.state != "canary":
                raise ProtocolError("canary has not started")
            if not self._quorum_ok(rs):
                raise ProtocolError("quorum lost")
            if not self._trust_ok(rs):
                raise ProtocolError("trust below tau")
            rs.canary_passed = True
            self._append("pass_canary", rule, agent)
            return self.snapshot_locked()

    def promote(self, agent: str, rule: str) -> dict[str, Any]:
        with self.lock:
            rs = self._rule(rule)
            self._require_agent(agent)
            if agent != self.policy_agent:
                raise ProtocolError("only the policy agent may promote")
            if rs.state != "canary":
                raise ProtocolError("promotion requires a canary")
            if not rs.canary_passed:
                raise ProtocolError("canary has not passed")
            if not self._quorum_ok(rs):
                raise ProtocolError("quorum lost")
            if not self._trust_ok(rs):
                raise ProtocolError("trust below tau")
            rs.state = "promoted"
            rs.promoted_tick = self.tick_no
            self.audited.add(rule)
            self._append("promote", rule, agent)
            return self.snapshot_locked()

    def retire(self, rule: str, agent: str | None = None, reason: str = "manual") -> dict[str, Any]:
        with self.lock:
            rs = self._rule(rule)
            if rs.state not in ("canary", "promoted"):
                raise ProtocolError("only an active candidate can be retired")
            rs.state = "retired"
            rs.retired_tick = self.tick_no
            self._append("retire", rule, agent, reason)
            return self.snapshot_locked()

    def reject(self, rule: str, agent: str | None = None) -> dict[str, Any]:
        with self.lock:
            rs = self._rule(rule)
            if rs.state != "observed":
                raise ProtocolError("only an observed candidate can be rejected")
            rs.state = "rejected"
            self._append("reject", rule, agent)
            return self.snapshot_locked()

    def tick(self) -> dict[str, Any]:
        with self.lock:
            self.tick_no += 1
            retired: list[str] = []
            for name, rs in self.rules.items():
                if rs.state == "promoted" and rs.trust <= self.tau:
                    rs.trust = 0
                    rs.state = "retired"
                    rs.retired_tick = self.tick_no
                    self._append("auto_retire", name, "scheduler", "trust floor")
                    retired.append(name)
                elif rs.trust > 0:
                    rs.trust -= 1
            self._append("tick", None, "scheduler", ",".join(retired))
            return self.snapshot_locked()

    # -- queries ---------------------------------------------------------
    def invariants_locked(self) -> dict[str, bool]:
        rules = self.rules
        active = self.active_locked()
        return {
            "NoPromotionWithoutCanary": all(
                rs.state != "promoted" or rs.canary_passed for rs in rules.values()
            ),
            "NoPromotionWithoutQuorum": all(
                rs.state != "promoted" or len(rs.votes) >= self.quorum for rs in rules.values()
            ),
            "NoPromotionWithoutTrust": all(
                rs.state != "promoted" or rs.trust >= self.tau for rs in rules.values()
            ),
            "ActiveImpliesAudited": active <= self.audited,
            "RetiredNotActive": all(
                rs.state != "retired" or name not in active for name, rs in rules.items()
            ),
            "TrustBounded": all(0 <= rs.trust <= self.max_trust for rs in rules.values()),
        }

    def active_locked(self) -> set[str]:
        return {name for name, rs in self.rules.items() if rs.state == "promoted"}

    def snapshot_locked(self) -> dict[str, Any]:
        active = self.active_locked()
        return {
            "tick": self.tick_no,
            "active": sorted(active),
            "audit_count": len(self.audited),
            "rules": {name: rs.snapshot() for name, rs in self.rules.items()},
            "invariants": self.invariants_locked(),
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return self.snapshot_locked()

    def audit(self) -> dict[str, Any]:
        with self.lock:
            return {
                "records": list(self._records),
                "counts": dict(self._counts),
                "seq": self._seq,
                "head": self._prev,
                "path": str(self.audit_path),
            }

    def verify_audit(self) -> dict[str, Any]:
        with self.lock:
            prev = GENESIS
            errors: list[str] = []
            seen_seq = 0
            for i, record in enumerate(self._records):
                body = {k: v for k, v in record.items() if k != "hash"}
                expected = hashlib.sha256(
                    prev.encode("ascii") + self._canonical(body)
                ).hexdigest()
                if record["prev"] != prev:
                    errors.append(f"record {i}: prev mismatch")
                if record["hash"] != expected:
                    errors.append(f"record {i}: hash mismatch")
                if record["seq"] != seen_seq:
                    errors.append(f"record {i}: seq gap ({record['seq']} != {seen_seq})")
                prev = record["hash"]
                seen_seq += 1
            return {
                "records": len(self._records),
                "head": prev,
                "chain_ok": not errors,
                "errors": errors[:20],
                "counts": dict(self._counts),
            }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CPPP-sidecar/1.0"

    # injected by make_server
    sidecar: Sidecar

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            raise ProtocolError("invalid JSON body") from None

    def _dispatch(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        s = self.sidecar
        if action == "validate":
            return s.validate(str(body.get("agent", "")), str(body.get("rule", "")))
        if action == "canary_start":
            return s.start_canary(str(body.get("rule", "")), body.get("agent"))
        if action == "canary_pass":
            return s.pass_canary(str(body.get("rule", "")), body.get("agent"))
        if action == "promote":
            return s.promote(str(body.get("agent", "")), str(body.get("rule", "")))
        if action == "retire":
            return s.retire(str(body.get("rule", "")), body.get("agent"), str(body.get("reason", "manual")))
        if action == "reject":
            return s.reject(str(body.get("rule", "")), body.get("agent"))
        if action == "tick":
            return s.tick()
        raise ProtocolError(f"unknown action {action!r}")

    def do_GET(self) -> None:  # noqa: N802
        started = time.perf_counter_ns()
        path = self.path.split("?", 1)[0]
        try:
            if path == "/health":
                self._json(200, {"ok": True, "server_ns": time.perf_counter_ns() - started})
            elif path == "/state":
                self._json(200, {"ok": True, "state": self.sidecar.snapshot(),
                                 "server_ns": time.perf_counter_ns() - started})
            elif path == "/audit":
                self._json(200, {"ok": True, "audit": self.sidecar.audit(),
                                 "server_ns": time.perf_counter_ns() - started})
            elif path == "/audit/verify":
                self._json(200, {"ok": True, "verification": self.sidecar.verify_audit(),
                                 "server_ns": time.perf_counter_ns() - started})
            else:
                self._json(404, {"ok": False, "error": "not found"})
        except ProtocolError as exc:
            self._json(409, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        started = time.perf_counter_ns()
        path = self.path.split("?", 1)[0]
        actions = {
            "/validate": "validate",
            "/canary/start": "canary_start",
            "/canary/pass": "canary_pass",
            "/promote": "promote",
            "/retire": "retire",
            "/reject": "reject",
            "/tick": "tick",
        }
        action = actions.get(path)
        if action is None:
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            body = self._read()
            state = self._dispatch(action, body)
            self._json(200, {"ok": True, "state": state,
                             "server_ns": time.perf_counter_ns() - started})
        except ProtocolError as exc:
            self._json(409, {"ok": False, "error": str(exc),
                             "server_ns": time.perf_counter_ns() - started})
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                             "server_ns": time.perf_counter_ns() - started})


def make_server(sidecar: Sidecar, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"sidecar": sidecar})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--agents", default="agent-a,agent-b,agent-c,policy")
    parser.add_argument("--policy-agent", default="policy")
    parser.add_argument("--rules", default="rule-1,rule-2,rule-3")
    parser.add_argument("--quorum", type=int, default=2)
    parser.add_argument("--tau", type=int, default=2)
    parser.add_argument("--max-trust", type=int, default=4)
    parser.add_argument("--audit", default="experiments/results/cppp/audit.jsonl")
    parser.add_argument("--no-fsync", action="store_true")
    args = parser.parse_args()

    sidecar = Sidecar(
        agents=[a.strip() for a in args.agents.split(",") if a.strip()],
        policy_agent=args.policy_agent,
        rules=[r.strip() for r in args.rules.split(",") if r.strip()],
        quorum=args.quorum,
        tau=args.tau,
        max_trust=args.max_trust,
        audit_path=Path(args.audit),
        fsync=not args.no_fsync,
    )
    server = make_server(sidecar, args.host, args.port)
    print(f"CPPP sidecar on http://{args.host}:{args.port} audit={args.audit}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
