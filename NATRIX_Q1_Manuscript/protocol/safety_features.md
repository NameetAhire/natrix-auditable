# Features retained by design (safety exceptions)

The fourth condition of the pre-registered drop rule excludes features that the
runtime uses as direct security policy signals, regardless of their statistical
importance. Dropping one of these from the ML contract would not remove the
policy rule, but it would make the audit's "no value" conclusion misleading:
the feature still has an operational role.

This list was fixed before the multivariate results were inspected and before
any leave-one-feature-out ablation was run.

| feature | runtime role |
|---|---|
| `sql_keyword_score` | SQL-injection rule in `proxy/server.js` |
| `xss_keyword_score` | XSS rule in `proxy/server.js` |
| `path_traversal_score` | traversal rule in `proxy/server.js` |
| `command_injection_score` | command-injection / RCE rule in `proxy/server.js` |
| `null_byte_score` | null-byte poisoning rule in `proxy/server.js` |
| `request_method_risk` | unsafe-method rule (TRACE/CONNECT/TRACK/DEBUG) |
| `user_agent_anomaly` | scanner / attack-tool User-Agent block |

Any feature on this list is marked `retained_safety` in
`artifacts/feature_selection/drop_evidence.csv` even if all three statistical
conditions would otherwise hold.
