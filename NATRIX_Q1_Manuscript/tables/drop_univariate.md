# Univariate screen (CSIC 2010)

Zero fractions are the proportion of exact zeros in each class. The
decision column repeats the four-condition verdict; the multivariate
evidence is in `drop_multivariate.md`.

| feature | group | p (BH) | Cliff $\delta$ | zero clean | zero attack | decision |
|---|---|---:|---:|---:|---:|---|
| `param_pollution_count` | structural | 1 | +0.0000 | 1.000 | 1.000 | **dropped** |
| `html_tag_density` | structural | 1 | +0.0000 | 1.000 | 1.000 | **dropped** |
| `uppercase_ratio` | shape | <1e-300 | +0.2979 | 0.001 | 0.057 | **retained** |
| `hex_encoding_ratio` | evasion | <1e-300 | +0.3861 | 0.379 | 0.208 | **retained** |
| `digit_ratio` | shape | 7.1e-171 | +0.1737 | 0.000 | 0.014 | **retained** |
| `payload_length` | shape | 3.85e-05 | +0.0260 | 0.000 | 0.000 | **retained** |
| `max_value_special_ratio` | lexical | <1e-300 | +0.3380 | 0.359 | 0.204 | **retained** |
| `shannon_entropy` | shape | 6.9e-76 | +0.1150 | 0.000 | 0.000 | **retained** |
| `special_char_ratio` | shape | 1.03e-180 | +0.1787 | 0.000 | 0.000 | **retained** |
| `sql_keyword_score` | signature | 9.3e-21 | +0.0421 | 0.795 | 0.758 | **retained** |
| `max_value_length` | lexical | 7.15e-57 | +0.0990 | 0.001 | 0.101 | **retained** |
| `double_escape_count` | lexical | <1e-300 | +0.1255 | 1.000 | 0.875 | **retained** |
| `quote_count` | lexical | <1e-300 | +0.1808 | 0.989 | 0.810 | **retained** |
| `request_method_risk` | behavioral | 1.14e-09 | -0.0332 | 0.000 | 0.000 | **retained** |
| `suspicious_extension_flag` | lexical | 2.88e-262 | +0.0625 | 1.000 | 0.938 | **retained** |
| `xss_keyword_score` | signature | 6.27e-127 | +0.0305 | 1.000 | 0.970 | **retained** |
| `path_traversal_score` | signature | 7.35e-36 | +0.0084 | 1.000 | 0.992 | **retained** |
| `user_agent_anomaly` | signature | 1 | +0.0000 | 1.000 | 1.000 | **retained** |
| `command_injection_score` | evasion | 7.35e-36 | +0.0084 | 1.000 | 0.992 | **retained** |
| `null_byte_score` | evasion | 1 | +0.0000 | 1.000 | 1.000 | **retained** |
| `angle_count` | lexical | 1.43e-233 | +0.0558 | 1.000 | 0.944 | **retained** |
| `token_count` | shape | 1 | -0.0415 | 0.000 | 0.000 | **retained** |
