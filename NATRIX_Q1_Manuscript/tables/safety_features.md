# Safety-retained features (pre-registered exception list)

These seven features are excluded from the statistical drop rule because the
runtime uses them as direct policy signals. Removing one from the model contract
would not remove the policy rule; it would only make the audit's "no statistical
value" conclusion misleading. The list was frozen before multivariate results
or leave-one-out ablation were inspected.

| feature | runtime role |
|---|---|
| `sql_keyword_score` | SQL-injection rule |
| `xss_keyword_score` | XSS rule |
| `path_traversal_score` | path-traversal rule |
| `command_injection_score` | command-injection / RCE rule |
| `null_byte_score` | null-byte poisoning rule |
| `request_method_risk` | unsafe-method rule (TRACE/CONNECT/TRACK/DEBUG) |
| `user_agent_anomaly` | scanner / attack-tool User-Agent block |

Source: `protocol/safety_features.md`; verdicts in
`artifacts/feature_selection/drop_evidence.csv`.
