# Live enforcement check

- Generated: `2026-11-18T05:27:07.405209+00:00`
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
| Benign latency p50 / p95 | 459.5 / 678.0 ms |
| Attack latency p50 / p95 | 404.9 / 936.5 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 477.4 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 619.0 ms | campaign query |
| `benign_projects` | benign | 404 | no | 517.4 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 414.0 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 218.1 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 60.3 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 678.0 ms | ordinary search |
| `benign_page` | benign | 200 | no | 410.5 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 352.4 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 459.5 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 309.3 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 882.3 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 184.6 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 404.9 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 248.7 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 228.6 ms | command injection |
| `null_byte` | attack | 403 | yes | 438.9 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 537.6 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 936.5 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 295.0 ms | JNDI lookup |

## Deployed gate

- Contract: `v4` (20-D), available: **True**
- Decisions: 13, enforced blocks: 4
- Inference p50 / p95 / p99: 0.8625 / 10.8908 / 10.8908 ms

> Labelled live policy check on a small probe set; not a generalisation estimate.
