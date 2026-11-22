# Live enforcement check

- Generated: `2026-11-18T04:55:02.782022+00:00`
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
| Benign latency p50 / p95 | 543.0 / 725.0 ms |
| Attack latency p50 / p95 | 444.4 / 696.2 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 628.6 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 725.0 ms | campaign query |
| `benign_projects` | benign | 404 | no | 543.0 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 513.4 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 544.4 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 97.9 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 521.9 ms | ordinary search |
| `benign_page` | benign | 200 | no | 707.0 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 421.7 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 420.8 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 368.4 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 696.2 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 176.1 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 356.2 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 199.5 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 297.5 ms | command injection |
| `null_byte` | attack | 403 | yes | 444.4 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 447.8 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 518.2 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 532.3 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
