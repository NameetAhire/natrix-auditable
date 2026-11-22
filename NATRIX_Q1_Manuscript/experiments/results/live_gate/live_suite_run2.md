# Live enforcement check

- Generated: `2026-11-16T05:47:38.418274+00:00`
- Gateway: `https://natrix-security-engine.onrender.com/p/nameetahire-vercel-app`
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
| Benign latency p50 / p95 | 1028.9 / 1523.4 ms |
| Attack latency p50 / p95 | 406.2 / 724.5 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 1030.7 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 1101.9 ms | campaign query |
| `benign_projects` | benign | 404 | no | 990.3 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 905.3 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 1523.4 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 228.8 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 1028.9 ms | ordinary search |
| `benign_page` | benign | 200 | no | 1019.1 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 1148.5 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 816.0 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 282.3 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 402.3 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 268.8 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 547.2 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 291.0 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 436.0 ms | command injection |
| `null_byte` | attack | 403 | yes | 724.5 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 429.4 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 314.9 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 406.2 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
