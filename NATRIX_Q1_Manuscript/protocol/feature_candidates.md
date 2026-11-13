# v4 candidate pool — pre-registered

Frozen before v4 screening. Candidates are drawn from (a) the WAF/HTTP-anomaly
literature and (b) fields the inline proxy already has. None was chosen by
inspecting CSIC label correlations.

Every candidate is computed from the same bounded inspection window
(`MAX_PAYLOAD_CHARS = 8192`) as v3, so the latency argument stays valid.

## Group A — request shape (no parsing cost beyond what v3 already does)

| id | definition | rationale |
|---|---|---|
| `url_depth` | number of `/` segments in the path | deep paths are common in traversal and scanner traffic |
| `query_param_count` | number of distinct query keys | scanners enumerate parameters |
| `body_param_count` | number of distinct form-body keys | mass-assignment and injection surfaces |
| `header_count` | number of request headers | minimal or bloated header sets both signal automation |
| `content_length_mismatch` | declared `Content-Length` minus observed body length, clipped at 0 | request smuggling / truncation |
| `body_to_url_ratio` | body length / (url length + 1) | upload and injection asymmetry |

## Group B — lexical composition

| id | definition | rationale |
|---|---|---|
| `semicolon_count` | raw + percent-encoded `;` | SQL stacking, command separators |
| `backslash_count` | raw + encoded `\` | Windows path traversal, escape sequences |
| `brace_count` | `{` `}` raw + encoded | JSON/NoSQL/template injection |
| `dollar_count` | `$` raw + encoded | shell substitution, jQuery/JS injection, template engines |
| `percent_ratio` | fraction of characters that are `%` | encoding abuse |
| `longest_token_length` | longest run without a delimiter | base64 payloads, hashes, uploaded blobs |
| `punctuation_diversity` | number of distinct non-alphanumeric characters / 32 | obfuscation diversity |
| `nonascii_ratio` | fraction of code points > 127 | homoglyph and encoding evasion |

## Group C — parameter-value semantics

| id | definition | rationale |
|---|---|---|
| `max_param_name_entropy` | Shannon entropy of the longest parameter name | generated/fuzzed parameter names |
| `param_name_digit_ratio` | digit fraction across all parameter names | auto-generated names |
| `value_type_mismatch` | 1 if a parameter that is numeric on the site's clean traffic carries non-numeric characters | type-confusion injection |
| `duplicate_value_count` | repeated identical values across parameters | replay / pollution |
| `empty_value_ratio` | empty values / total values | probing and fuzzing |

## Group D — protocol and header coherence

| id | definition | rationale |
|---|---|---|
| `missing_host` | 1 if `Host` absent | HTTP/1.0 tooling, smuggling |
| `ua_header_mismatch` | 1 if UA claims a browser but `Accept-Language`/`Accept` are absent | scripted clients |
| `content_type_form_mismatch` | body looks like `k=v&...` but `Content-Type` is not form/multipart | parser-differential evasion |
| `expect_100_continue` | 1 if `Expect: 100-continue` present | smuggling and slowloris tooling |
| `transfer_encoding_present` | 1 if `Transfer-Encoding` present | request smuggling |
| `absolute_uri_in_target` | 1 if the request target is an absolute URI | proxy abuse, SSRF |

## Group E — attack-family signals not covered by v3

| id | definition | rationale |
|---|---|---|
| `ldap_filter_score` | count of `)(`, `objectClass`, `uid=`, `cn=` patterns | LDAP injection (ECML family) |
| `xpath_score` | count of `count(`, `local-name(`, `node()`, `string-length(` | XPath injection (ECML family) |
| `ssi_directive_score` | count of `<!--#`, `#echo`, `#exec`, `#include` | SSI injection (ECML family) |
| `nosql_operator_score` | count of `$ne`, `$gt`, `$where`, `$regex` | NoSQL injection |
| `template_expression_score` | count of `{{`, `${`, `<%=` | SSTI |
| `log4shell_score` | count of `${jndi:`, `ldap://`, `rmi://` | Log4Shell family |
| `crlf_sequence_count` | count of `%0d%0a`, `\r\n` | response splitting |

## Screening protocol

1. Compute all candidates for every corpus.
2. Remove candidates that are near-constant on **all** corpora (zero variance).
3. Remove candidates with |Spearman| ≥ 0.95 against an already-retained feature,
   keeping the cheaper one.
4. Nested CV: add candidates one at a time to the retained v3 core, inside the
   training fold, and keep a candidate only if the inner-fold mean F1 improves
   by more than its own standard error across the inner folds.
5. Final v4 = retained v3 core + accepted candidates. Report the whole path,
   including rejected candidates, in the paper appendix.

## Cost budget

Each candidate must add ≤ 0.15 ms to Python extraction p95 and ≤ 0.05 ms to Node
extraction p95, measured on the 8 KiB worst case. Any candidate that violates the
budget is rejected regardless of accuracy.
