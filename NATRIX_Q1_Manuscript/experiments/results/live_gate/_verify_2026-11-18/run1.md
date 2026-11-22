# Live enforcement check

- Generated: `2026-11-18T04:28:54.544908+00:00`
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
| Benign latency p50 / p95 | 1135.2 / 1721.2 ms |
| Attack latency p50 / p95 | 310.1 / 461.9 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 1721.2 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 1492.1 ms | campaign query |
| `benign_projects` | benign | 404 | no | 1444.5 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 930.1 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 813.8 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 289.7 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 1372.2 ms | ordinary search |
| `benign_page` | benign | 200 | no | 931.9 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 1135.2 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 927.4 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 259.0 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 282.0 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 251.6 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 371.4 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 250.6 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 439.0 ms | command injection |
| `null_byte` | attack | 403 | yes | 461.9 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 379.1 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 310.1 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 270.5 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
