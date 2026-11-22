# Live enforcement check

- Generated: `2026-11-18T04:29:41.367599+00:00`
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
| Benign latency p50 / p95 | 866.7 / 1136.0 ms |
| Attack latency p50 / p95 | 284.0 / 609.1 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 998.2 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 614.6 ms | campaign query |
| `benign_projects` | benign | 404 | no | 866.7 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 1136.0 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 667.4 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 284.8 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 502.2 ms | ordinary search |
| `benign_page` | benign | 200 | no | 521.3 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 1032.7 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 934.7 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 248.1 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 284.0 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 261.3 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 293.6 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 269.3 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 244.7 ms | command injection |
| `null_byte` | attack | 403 | yes | 609.1 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 285.3 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 348.4 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 247.2 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
