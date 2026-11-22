# Verification runs, 2026-11-18

Fixed 20-probe enforcement suite (`experiments/scripts/live_attack_suite.py`).
Benign probes are sent first so adaptive blocking cannot contaminate the
false-positive count. This is a policy check, not a generalisation estimate.

## Render gateway

Target: `https://natrix-security-engine.onrender.com/p/nameetahire-vercel-app`

| Runs | TP | FP | TN | FN | FPR | Origin rendered |
|------|----|----|----|----|-----|-----------------|
| 3    | 30 | 0  | 30 | 0  | 0.0 | yes (all) |

`run1.json` to `run3.json` are the artefacts. Gate counters and the persisted
decision ledger were not read: the rotated `NATRIX_ADMIN_KEY` was not
available, so `/api/gate/stats` and `/api/gate/export` returned 401.

## Local Docker stack

Target: `http://localhost:3000/p/nameetahire-vercel-app`

| Runs | TP | FP | TN | FN | FPR | Origin rendered |
|------|----|----|----|----|-----|-----------------|
| 3    | 30 | 0  | 30 | 0  | 0.0 | yes (all) |

`local_run1` used the normal proxy. `local_run2` and `local_run3` used a
one-off proxy container started with `NATRIX_ADMIN_KEY=localtest`; the key is
not stored in the repository. `local_run4` repeats the suite against that
container to populate the dashboard and records the same TP=10/FP=0/TN=10/FN=0.

`local_run3.json` records the gate counters around the run:

- contract `v4`, `feature_count` 20, ONNX `models/csic_binary_20d/gate_20d.onnx`, threshold 0.5
- decisions 15 -> 27, enforced blocks 4 -> 8
- gate latency p50 1.06 ms, p95 4.65 ms, p99 21.89 ms

The gate scored every request that reached it as an attack, including benign
ones; enforcement allowed the benign requests. The zero-FP audit result is
therefore a composition effect of rules, allow-listing, and enforcement, not
detector calibration. The paper states this limit.

## What is not claimed

- No adaptive-adversary evaluation.
- No live shadow-mode traffic; the probe set is fixed and labelled by hand.
- The shipped proxy does not implement CPPP; the formal suite and sidecar
  evidence describe the specified protocol.
