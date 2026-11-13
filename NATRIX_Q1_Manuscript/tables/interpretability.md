# Interpretability audit (CSIC 2010, P1, 5 folds)

Permutation importance is the mean over folds with a 95% bootstrap CI;
mean absolute SHAP is the mean over 500 held-out records per fold.
A zero SHAP value means the forest never split on the feature in that
fold; it does not mean the runtime policy ignores the signal.

| rank | feature | group | $p_{BH}$ | Cliff's $\delta$ | permutation importance (95% CI) | mean abs SHAP | decision |
|---:|---|---|---:|---:|---|---:|---|
| 1 | `uppercase_ratio` | shape | $<10^{-300}$ | +0.298 | 0.2716 [0.2661, 0.2772] | 0.1429 | retained |
| 2 | `hex_encoding_ratio` | evasion | $<10^{-300}$ | +0.386 | 0.2069 [0.1994, 0.2145] | 0.0838 | retained |
| 3 | `digit_ratio` | shape | 7.1e-171 | +0.174 | 0.1375 [0.1196, 0.1554] | 0.0372 | retained |
| 4 | `payload_length` | shape | 3.85e-05 | +0.026 | 0.1090 [0.0923, 0.1256] | 0.0402 | retained |
| 5 | `max_value_special_ratio` | lexical | $<10^{-300}$ | +0.338 | 0.1043 [0.1030, 0.1057] | 0.0528 | retained |
| 6 | `shannon_entropy` | shape | 6.9e-76 | +0.115 | 0.0938 [0.0501, 0.1375] | 0.0220 | retained |
| 7 | `special_char_ratio` | shape | 1.03e-180 | +0.179 | 0.0831 [0.0684, 0.0979] | 0.0306 | retained |
| 8 | `sql_keyword_score` | signature | 9.3e-21 | +0.042 | 0.0758 [0.0724, 0.0792] | 0.0637 | retained |
| 9 | `max_value_length` | lexical | 7.15e-57 | +0.099 | 0.0547 [0.0501, 0.0592] | 0.0174 | retained |
| 10 | `double_escape_count` | lexical | $<10^{-300}$ | +0.125 | 0.0235 [0.0204, 0.0266] | 0.0207 | retained |
| 11 | `quote_count` | lexical | $<10^{-300}$ | +0.181 | 0.0089 [0.0070, 0.0108] | 0.0070 | retained |
| 12 | `request_method_risk` | behavioral | 1.14e-09 | -0.033 | 0.0089 [0.0078, 0.0099] | 0.0083 | retained |
| 13 | `suspicious_extension_flag` | lexical | 2.88e-262 | +0.062 | 0.0000 [-0.0001, 0.0001] | 0.0008 | retained |
| 17 | `param_pollution_count` | structural | 1 | +0.000 | 0.0000 [0.0000, 0.0000] | 0.0000 | dropped |
| 17 | `html_tag_density` | structural | 1 | +0.000 | 0.0000 [0.0000, 0.0000] | 0.0000 | dropped |
| 17 | `xss_keyword_score` | signature | 6.27e-127 | +0.030 | 0.0000 [0.0000, 0.0000] | 0.0000 | retained |
| 17 | `path_traversal_score` | signature | 7.35e-36 | +0.008 | 0.0000 [0.0000, 0.0000] | 0.0000 | retained |
| 17 | `user_agent_anomaly` | signature | 1 | +0.000 | 0.0000 [0.0000, 0.0000] | 0.0000 | retained |
| 17 | `command_injection_score` | evasion | 7.35e-36 | +0.008 | 0.0000 [0.0000, 0.0000] | 0.0000 | retained |
| 17 | `null_byte_score` | evasion | 1 | +0.000 | 0.0000 [0.0000, 0.0000] | 0.0000 | retained |
| 17 | `angle_count` | lexical | 1.43e-233 | +0.056 | 0.0000 [0.0000, 0.0000] | 0.0000 | retained |
| 22 | `token_count` | shape | 1 | -0.041 | -0.0005 [-0.0008, -0.0003] | 0.0012 | retained |

Features with zero mean $|$SHAP$|$ on CSIC: `param_pollution_count`, `html_tag_density`, `path_traversal_score`, `user_agent_anomaly`, `command_injection_score`, `null_byte_score`.
Of these, `command_injection_score` and `path_traversal_score` are
non-zero on only 0.84% of CSIC attacks; the rest are constant on this
corpus. All are safety-retained except the two dropped features.
