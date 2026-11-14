# Gate C: per-candidate cost and the set-level budget

The ten most expensive candidates are shown.

| candidate | Gate B accepted | marginal p95 (ms) | marginal <= 0.15 ms |
|---|---|---:|---|
| `max_param_name_entropy` | yes | 0.480 | no |
| `punctuation_diversity` | no | 0.472 | no |
| `longest_token_length` | yes | 0.351 | no |
| `nonascii_ratio` | yes | 0.257 | no |
| `param_name_digit_ratio` | yes | 0.117 | yes |
| `ldap_filter_score` | yes | 0.014 | yes |
| `brace_count` | yes | 0.013 | yes |
| `crlf_sequence_count` | yes | 0.008 | yes |
| `empty_value_ratio` | yes | 0.003 | yes |
| `url_depth` | yes | 0.002 | yes |

| set | features | p95 (ms) | within 0.15 ms |
|---|---:|---:|---|
| all candidates | 24 | 2.33 | no |
| Gate B accepted | 12 | 1.71 | no |
| accepted, marginal <= 0.15 ms | 9 | 0.73 | no |

The ten most expensive candidates are shown. The set rows include the second parse because the candidate extractor is an additional pass over the payload. The budget applies to the admitted block, so selecting the cheap subset after inspecting this table would be the post-hoc search the protocol forbids.
