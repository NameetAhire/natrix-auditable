# Live enforcement check

- Generated: `2026-11-18T04:53:11.854651+00:00`
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
| Benign latency p50 / p95 | 331.6 / 853.0 ms |
| Attack latency p50 / p95 | 260.2 / 818.8 ms |

## Probes

| Probe | Expected | Status | Blocked | Latency | Note |
|---|---|---|---|---|---|
| `benign_home` | benign | 200 | no | 853.0 ms | portfolio homepage |
| `benign_utm` | benign | 200 | no | 519.6 ms | campaign query |
| `benign_projects` | benign | 404 | no | 419.0 ms | SPA route (origin 404 is still allowed) |
| `benign_about` | benign | 404 | no | 278.2 ms | SPA route (origin 404 is still allowed) |
| `benign_js` | benign | 200 | no | 843.5 ms | production JS bundle |
| `benign_css` | benign | 200 | no | 312.6 ms | production CSS bundle |
| `benign_search` | benign | 200 | no | 242.6 ms | ordinary search |
| `benign_page` | benign | 200 | no | 230.5 ms | pagination |
| `benign_apostrophe` | benign | 200 | no | 276.5 ms | surname with apostrophe |
| `benign_email` | benign | 200 | no | 331.6 ms | email parameter |
| `sqli_union` | attack | 403 | yes | 111.8 ms | SQL injection |
| `sqli_or` | attack | 403 | yes | 818.8 ms | SQL injection |
| `xss_script` | attack | 403 | yes | 123.5 ms | reflected XSS |
| `xss_svg` | attack | 403 | yes | 259.7 ms | XSS that evaded the rules |
| `traversal` | attack | 403 | yes | 291.6 ms | path traversal |
| `cmd_injection` | attack | 403 | yes | 101.2 ms | command injection |
| `null_byte` | attack | 403 | yes | 247.7 ms | null-byte extension bypass |
| `double_encoded` | attack | 403 | yes | 260.2 ms | double-encoded traversal |
| `scanner_path` | attack | 403 | yes | 594.5 ms | vulnerability scanner |
| `log4shell` | attack | 403 | yes | 349.0 ms | JNDI lookup |

> Labelled live policy check on a small probe set; not a generalisation estimate.
