# Live enforcement check

- Generated: `2026-11-18T04:29:22.159097+00:00`
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
| Benign latency p50 / p95 | 873.6 / 1000.2 ms |
| Attack latency p50 / p95 | 289.0 / 433.8 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 651.2 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 521.4 ms | campaign query |
| `benign_projects` | benign | 404 | no | 759.3 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 1000.2 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 746.3 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 202.4 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 967.3 ms | ordinary search |
| `benign_page` | benign | 200 | no | 980.9 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 929.1 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 873.6 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 282.0 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 293.6 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 208.2 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 334.3 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 248.0 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 235.5 ms | command injection |
| `null_byte` | attack | 403 | yes | 289.0 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 386.2 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 276.2 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 433.8 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
