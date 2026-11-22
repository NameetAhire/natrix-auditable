# Live gate ledger inspection, 2026-11-18

Admin API read with the rotated production key. The key is not stored here.

## Gateway state

`GET /api/gate/stats` after one benign request:

- `available: true`, contract `v4`, `feature_count: 20`
- model `models/csic_binary_20d/gate_20d.onnx`, threshold 0.5
- one in-process decision, probability 1.0, allowed (`enforced_blocks: 0`)
- gate latency p50/p95 1.37 ms for that sample
- persisted ledger: 196 decisions, 196 positives, 44 enforced

## Ledger composition

`GET /api/gate/export` returned 195 rows before the benign request above
(2026-11-15T07:21Z to 2026-11-18T05:27Z). Every row has `is_attack = 1`.

| Source | Rows | Enforced | Notes |
|--------|------|----------|-------|
| Local Docker probes (`172.18.0.1`, `::1`) | 67 | 16 | our own test traffic |
| External fixed-suite probes | 124 | 28 | exact paths from `live_attack_suite.py` |
| Health/status checks (`/health`, `/api/health`, `/api/stats`) | 4 | 0 | non-probe, still scored attack |
| Organic browsing traffic | 0 | 0 | none in the ledger |

The 124 external probe rows are 96 benign probe requests and 28 attack
requests. All 96 benign requests scored attack and none was enforced. All 28
attack requests that reached the gate were enforced.

The four health/status checks also scored attack and were allowed.

## Consequence

There is no organic user traffic in the ledger. The production gateway has
been exercised only by the fixed 20-probe suite, local Docker runs, and
health checks. The ledger therefore cannot support a real-traffic
false-positive or false-negative estimate, and it should not be described as
shadow-mode evidence. The fixed-probe audit remains the only deployment
evidence.

The ledger also mixes local and production writes because both use the same
Turso database. Rows must be separated by `client_ip` before any analysis;
the persisted counters alone are not production-only.
