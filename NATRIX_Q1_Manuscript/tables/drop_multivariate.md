# Multivariate and ablation evidence (CSIC 2010)

Permutation importance is the mean over five folds; the CI is a 95%
bootstrap interval. Ablation removes one feature at a time from the
22-D gate. `failed` lists the conditions that prevented a drop; a
dropped feature has all four conditions satisfied.

| feature | perm. imp. (95% CI) | rank | $\Delta$acc (95% CI) | $\Delta$FPR | failed | decision |
|---|---|---:|---|---:|---|---|
| `param_pollution_count` | +0.0000 [+0.0000, +0.0000] | 17/22 | -0.01% [-0.08, +0.05] | -0.02% | none (all hold) | **dropped** |
| `html_tag_density` | +0.0000 [+0.0000, +0.0000] | 17/22 | -0.01% [-0.08, +0.05] | -0.02% | none (all hold) | **dropped** |
| `uppercase_ratio` | +0.2716 [+0.2661, +0.2772] | 1/22 | -1.08% [-1.30, -0.87] | +0.14% | C1, C2, C3 | **retained** |
| `hex_encoding_ratio` | +0.2069 [+0.1994, +0.2145] | 2/22 | -0.72% [-0.87, -0.57] | +0.42% | C1, C2, C3 | **retained** |
| `digit_ratio` | +0.1375 [+0.1196, +0.1554] | 3/22 | -0.88% [-1.03, -0.74] | +0.50% | C1, C2, C3 | **retained** |
| `payload_length` | +0.1090 [+0.0923, +0.1256] | 4/22 | -0.31% [-0.42, -0.19] | +0.02% | C1, C2, C3 | **retained** |
| `max_value_special_ratio` | +0.1043 [+0.1030, +0.1057] | 5/22 | -0.79% [-0.97, -0.62] | +0.49% | C1, C2, C3 | **retained** |
| `shannon_entropy` | +0.0938 [+0.0501, +0.1375] | 6/22 | -1.50% [-1.69, -1.34] | +1.13% | C1, C2, C3 | **retained** |
| `special_char_ratio` | +0.0831 [+0.0684, +0.0979] | 7/22 | +1.52% [+1.37, +1.68] | -0.24% | C1, C2 | **retained** |
| `sql_keyword_score` | +0.0758 [+0.0724, +0.0792] | 8/22 | -0.07% [-0.15, +0.03] | +0.06% | C1, C2, C4 | **retained** |
| `max_value_length` | +0.0547 [+0.0501, +0.0592] | 9/22 | -0.72% [-0.85, -0.59] | +0.46% | C1, C2, C3 | **retained** |
| `double_escape_count` | +0.0235 [+0.0204, +0.0266] | 10/22 | -0.16% [-0.27, -0.06] | +0.15% | C1, C2, C3 | **retained** |
| `quote_count` | +0.0089 [+0.0070, +0.0108] | 11/22 | -0.06% [-0.15, +0.04] | +0.08% | C1, C2 | **retained** |
| `request_method_risk` | +0.0089 [+0.0078, +0.0099] | 12/22 | -0.70% [-0.82, -0.58] | +0.14% | C1, C2, C3, C4 | **retained** |
| `suspicious_extension_flag` | +0.0000 [-0.0001, +0.0001] | 13/22 | +0.01% [-0.06, +0.08] | -0.03% | C1, C2 | **retained** |
| `xss_keyword_score` | +0.0000 [+0.0000, +0.0000] | 17/22 | +0.02% [-0.04, +0.08] | -0.05% | C1, C4 | **retained** |
| `path_traversal_score` | +0.0000 [+0.0000, +0.0000] | 17/22 | -0.03% [-0.09, +0.03] | +0.02% | C4 | **retained** |
| `user_agent_anomaly` | +0.0000 [+0.0000, +0.0000] | 17/22 | -0.01% [-0.07, +0.06] | +0.02% | C4 | **retained** |
| `command_injection_score` | +0.0000 [+0.0000, +0.0000] | 17/22 | -0.01% [-0.08, +0.06] | +0.02% | C4 | **retained** |
| `null_byte_score` | +0.0000 [+0.0000, +0.0000] | 17/22 | -0.01% [-0.08, +0.05] | -0.02% | C4 | **retained** |
| `angle_count` | +0.0000 [+0.0000, +0.0000] | 17/22 | -0.05% [-0.11, +0.01] | +0.07% | C1 | **retained** |
| `token_count` | -0.0005 [-0.0008, -0.0003] | 22/22 | +0.03% [-0.03, +0.09] | +0.02% | C2 | **retained** |
