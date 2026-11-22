# Live enforcement check

- Generated: `2026-11-16T05:46:52.596842+00:00`
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
| Benign latency p50 / p95 | 1085.4 / 1303.1 ms |
| Attack latency p50 / p95 | 321.3 / 621.0 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 814.8 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 526.9 ms | campaign query |
| `benign_projects` | benign | 404 | no | 1085.4 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 1303.1 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 1261.9 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 635.1 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 1193.7 ms | ordinary search |
| `benign_page` | benign | 200 | no | 985.0 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 717.8 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 1195.4 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 576.8 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 460.4 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 321.3 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 621.0 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 266.6 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 294.8 ms | command injection |
| `null_byte` | attack | 403 | yes | 497.7 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 224.4 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 304.4 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 267.1 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
