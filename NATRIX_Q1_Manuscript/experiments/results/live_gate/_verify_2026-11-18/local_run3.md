# Live enforcement check

- Generated: `2026-11-18T04:56:45.779517+00:00`
- Gateway: `http://localhost:3000/p/nameetahire-vercel-app`
- Origin rendered the portfolio: **True** (`Nameet Ahire | AI/ML Engineer & Cloud DevOps Architect Portfolio`)

## Confusion matrix (labelled probes)

| | Blocked | Allowed |
|---|---|---|
| Attack | 10 (TP) | 0 (FN) |
| Benign | 0 (FP) | 10 (TN) |

| Metric | Value |
|---|---|
| Accuracy | 1.0 |
| Precision | 1.0 |
| Recall | 1.0 |
| F1 | 1.0 |
| False-positive rate | 0.0 |
| False-negative rate | 0.0 |
| Benign latency p50 / p95 | 449.2 / 890.9 ms |
| Attack latency p50 / p95 | 389.1 / 685.9 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 695.0 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 403.1 ms | campaign query |
| `benign_projects` | benign | 404 | no | 416.9 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 517.4 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 343.5 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 57.8 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 825.2 ms | ordinary search |
| `benign_page` | benign | 200 | no | 890.9 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 444.8 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 449.2 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 295.1 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 685.9 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 267.1 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 421.1 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 178.4 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 188.6 ms | command injection |
| `null_byte` | attack | 403 | yes | 365.2 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 389.1 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 644.2 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 466.6 ms | JNDI lookup |

## Deployed gate

- Contract: `v4` (20-D), available: **True**
- Decisions: 27, enforced blocks: 8
- Inference p50 / p95 / p99: 1.0585 / 4.6468 / 21.8869 ms

> Labelled live policy check on a small probe set; not a generalisation estimate.
