# Live enforcement check

- Generated: `2026-11-16T05:48:21.510679+00:00`
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
| Benign latency p50 / p95 | 933.6 / 1069.9 ms |
| Attack latency p50 / p95 | 325.7 / 1271.4 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 984.9 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 800.6 ms | campaign query |
| `benign_projects` | benign | 404 | no | 464.4 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 1069.9 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 662.3 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 377.8 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 928.9 ms | ordinary search |
| `benign_page` | benign | 200 | no | 933.6 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 1020.1 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 949.2 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 325.7 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 415.7 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 256.2 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 250.9 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 253.7 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 351.8 ms | command injection |
| `null_byte` | attack | 403 | yes | 258.9 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 431.1 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 1271.4 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 262.3 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
