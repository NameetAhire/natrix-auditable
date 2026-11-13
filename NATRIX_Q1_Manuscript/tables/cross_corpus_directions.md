# Cross-corpus direction replication (22-D contract)

Cliff's $\delta$ is attack minus clean; positive means the feature is
larger in attacks. `direction` compares the sign with CSIC. The audit is
descriptive (D10); no feature is selected on these corpora.

| feature | CSIC $\delta$ | ECML $\delta$ | SR-BH $\delta$ | CSIC rank | ECML rank | SR-BH rank | direction |
|---|---:|---:|---:|---:|---:|---:|---|
| `uppercase_ratio` | +0.298 | +0.243 | -0.480 | 1/22 | 7/22 | 2/22 | mixed |
| `hex_encoding_ratio` | +0.386 | -0.537 | -0.417 | 2/22 | 4/22 | 1/22 | reversed |
| `digit_ratio` | +0.174 | -0.183 | -0.113 | 3/22 | 13/22 | 5/22 | reversed |
| `payload_length` | +0.026 | -0.276 | -0.418 | 4/22 | 8/22 | 3/22 | reversed |
| `max_value_special_ratio` | +0.338 | -0.362 | -0.030 | 5/22 | 6/22 | 15/22 | reversed |
| `shannon_entropy` | +0.115 | -0.018 | -0.234 | 6/22 | 12/22 | 7/22 | reversed |
| `special_char_ratio` | +0.179 | -0.695 | -0.223 | 7/22 | 2/22 | 4/22 | reversed |
| `sql_keyword_score` | +0.042 | -0.146 | -0.361 | 8/22 | 14/22 | 13/22 | reversed |
| `max_value_length` | +0.099 | -0.592 | -0.028 | 9/22 | 1/22 | 12/22 | reversed |
| `double_escape_count` | +0.125 | -0.027 | -0.106 | 10/22 | 14/22 | 14/22 | reversed |
| `quote_count` | +0.181 | -0.446 | -0.215 | 11/22 | 3/22 | 6/22 | reversed |
| `request_method_risk` | -0.033 | +0.017 | -0.062 | 12/22 | 16/22 | 10/22 | mixed |
| `suspicious_extension_flag` | +0.062 | -0.008 | +0.004 | 13/22 | 20/22 | 18/22 | mixed |
| `html_tag_density` | +0.000 | -0.018 | -0.000 | 17/22 | 18/22 | 20/22 | mixed |
| `command_injection_score` | +0.008 | -0.072 | +0.101 | 17/22 | 5/22 | 8/22 | mixed |
| `angle_count` | +0.056 | -0.243 | +0.020 | 17/22 | 11/22 | 11/22 | mixed |
| `param_pollution_count` | +0.000 | -0.000 | -0.000 | 17/22 | 20/22 | 20/22 | mixed |
| `null_byte_score` | +0.000 | -0.002 | +0.011 | 17/22 | 20/22 | 17/22 | mixed |
| `path_traversal_score` | +0.008 | -0.146 | +0.126 | 17/22 | 9/22 | 9/22 | mixed |
| `user_agent_anomaly` | +0.000 | +0.000 | -0.008 | 17/22 | 20/22 | 16/22 | mixed |
| `xss_keyword_score` | +0.030 | -0.074 | +0.012 | 17/22 | 17/22 | 19/22 | mixed |
| `token_count` | -0.041 | +0.001 | -0.053 | 22/22 | 10/22 | 22/22 | mixed |

Features with reversed direction in both corpora: `hex_encoding_ratio`, `digit_ratio`, `payload_length`, `max_value_special_ratio`, `shannon_entropy`, `special_char_ratio`, `sql_keyword_score`, `max_value_length`, `double_escape_count`, `quote_count`.
