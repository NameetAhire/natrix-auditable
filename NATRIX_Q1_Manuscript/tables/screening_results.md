# v4 candidate screening (nested, CSIC 2010)

Rule: mean $\Delta$F1 > its standard error across outer folds and
positive in at least 4/5 folds.

| candidate | mean delta F1 | SE | positive folds | accepted |
|---|---:|---:|---:|:--:|
| param_name_digit_ratio | +0.04459 | 0.00086 | 5/5 | yes |
| max_param_name_entropy | +0.00609 | 0.00062 | 5/5 | yes |
| longest_token_length | +0.00251 | 0.00044 | 5/5 | yes |
| url_depth | +0.00066 | 0.00018 | 5/5 | yes |
| dollar_count | +0.00061 | 0.00024 | 4/5 | yes |
| empty_value_ratio | +0.00052 | 0.00021 | 4/5 | yes |
| backslash_count | +0.00046 | 0.00023 | 4/5 | yes |
| brace_count | +0.00046 | 0.00023 | 4/5 | yes |
| crlf_sequence_count | +0.00046 | 0.00023 | 4/5 | yes |
| ldap_filter_score | +0.00046 | 0.00023 | 4/5 | yes |
| nonascii_ratio | +0.00046 | 0.00023 | 4/5 | yes |
| semicolon_count | +0.00039 | 0.00021 | 5/5 | yes |
| duplicate_value_count | -0.00006 | 0.00028 | 3/5 | no |
| body_param_count | -0.00033 | 0.00024 | 2/5 | no |
| query_param_count | -0.00033 | 0.00013 | 1/5 | no |
| punctuation_diversity | -0.00274 | 0.00019 | 0/5 | no |

**Adoption decision (D12).** The accuracy screen accepted the
candidates marked `yes`, but the pre-registered extraction-cost
budget fails: the candidate pass costs 2.28 ms p95 on the 8 KiB
worst case against a 0.15 ms budget. No candidate
is admitted; final v4 is the 20-D retained core. Five raw-accepted
candidates (`backslash_count`, `brace_count`, `nonascii_ratio`,
`ldap_filter_score`, `crlf_sequence_count`) are exactly constant on
CSIC, so their identical +0.046 pp gain is an RNG artefact.
