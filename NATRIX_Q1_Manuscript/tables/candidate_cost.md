# Gate C: measured extraction cost per candidate

Batch timing (10 calls per batch, 60 batches) on the 8 KiB
delimiter-heavy worst case. Marginal cost excludes the shared parse;
the set rows include it because the candidate extractor is an
additional pass over the payload. The budget is 0.15 ms for the
whole admitted block, not a per-feature allowance.

| candidate | accepted by Gate B | marginal p95 (ms) | typical p95 (ms) | marginal <= 0.15 ms |
|---|---|---:|---:|---|
| `max_param_name_entropy` | yes | 0.480 | 0.0060 | no |
| `punctuation_diversity` | no | 0.472 | 0.0019 | no |
| `longest_token_length` | yes | 0.351 | 0.0019 | no |
| `nonascii_ratio` | yes | 0.257 | 0.0015 | no |
| `param_name_digit_ratio` | yes | 0.117 | 0.0018 | yes |
| `ssi_directive_score` | no | 0.018 | 0.0011 | yes |
| `ldap_filter_score` | yes | 0.014 | 0.0011 | yes |
| `template_expression_score` | no | 0.013 | 0.0010 | yes |
| `brace_count` | yes | 0.013 | 0.0007 | yes |
| `semicolon_count` | yes | 0.012 | 0.0004 | yes |
| `log4shell_score` | no | 0.011 | 0.0009 | yes |
| `xpath_score` | no | 0.011 | 0.0011 | yes |
| `nosql_operator_score` | no | 0.011 | 0.0011 | yes |
| `crlf_sequence_count` | yes | 0.008 | 0.0004 | yes |
| `query_param_count` | no | 0.007 | 0.0004 | yes |
| `backslash_count` | yes | 0.006 | 0.0004 | yes |
| `dollar_count` | yes | 0.006 | 0.0004 | yes |
| `percent_ratio` | no | 0.004 | 0.0003 | yes |
| `empty_value_ratio` | yes | 0.003 | 0.0004 | yes |
| `absolute_uri_in_target` | no | 0.003 | 0.0002 | yes |
| `url_depth` | yes | 0.002 | 0.0002 | yes |
| `duplicate_value_count` | no | 0.002 | 0.0003 | yes |
| `body_to_url_ratio` | no | 0.000 | 0.0002 | yes |
| `body_param_count` | no | 0.000 | 0.0001 | yes |

## Set-level cost

| set | features | p95 (ms) |
|---|---:|---:|
| all candidates | 24 | 2.327 |
| Gate B accepted | 12 | 1.714 |
| accepted, marginal <= 0.15 ms | 9 | 0.725 |

The full pass is 2.33 ms and the Gate B accepted block is 1.71 ms,
both above the 0.15 ms envelope. Even the nine accepted candidates
whose marginal cost is below 0.15 ms cost 0.73 ms as a set because
each shares the second parse. The gate is therefore applied to the
block; selecting a cheap subset after inspecting this table would be
the post-hoc search the protocol forbids.
