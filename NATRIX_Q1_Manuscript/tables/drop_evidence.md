# Feature-drop evidence (Phase 2 appendix)

Drop rule (frozen in `protocol/analysis_plan.md`): a feature is removed
only when all four conditions hold — C1 univariate null or near-constant,
C2 permutation importance in the bottom quartile with a 95% CI containing
zero, C3 leave-one-feature-out ablation within the practical-equivalence
margin, and C4 not on the pre-registered safety list.

| feature | group | p (BH) | Cliff δ | perm. imp. | 95% CI | rank | Δacc | ΔFPR | C1 | C2 | C3 | C4 | decision |
|---|---|---:|---:|---:|---|---:|---:|---:|:--:|:--:|:--:|:--:|---|
| `param_pollution_count` | structural | 1 | +0.0000 | +0.000000 | [+0.000000, +0.000000] | 17/22 | -0.0116% | -0.0215% | yes | yes | yes | yes | **dropped** |
| `html_tag_density` | structural | 1 | +0.0000 | +0.000000 | [+0.000000, +0.000000] | 17/22 | -0.0116% | -0.0215% | yes | yes | yes | yes | **dropped** |
| `uppercase_ratio` | shape | <1e-300 | +0.2979 | +0.271622 | [+0.266065, +0.277179] | 1/22 | -1.0811% | +0.1448% | no | no | no | yes | **retained** |
| `hex_encoding_ratio` | evasion | <1e-300 | +0.3861 | +0.206935 | [+0.199381, +0.214489] | 2/22 | -0.7169% | +0.4185% | no | no | no | yes | **retained** |
| `digit_ratio` | shape | 7.1e-171 | +0.1737 | +0.137516 | [+0.119592, +0.155441] | 3/22 | -0.8846% | +0.5043% | no | no | no | yes | **retained** |
| `payload_length` | shape | 3.85e-05 | +0.0260 | +0.108982 | [+0.092343, +0.125620] | 4/22 | -0.3064% | +0.0161% | no | no | no | yes | **retained** |
| `max_value_special_ratio` | lexical | <1e-300 | +0.3380 | +0.104333 | [+0.102957, +0.105709] | 5/22 | -0.7950% | +0.4936% | no | no | no | yes | **retained** |
| `shannon_entropy` | shape | 6.9e-76 | +0.1150 | +0.093790 | [+0.050083, +0.137497] | 6/22 | -1.5032% | +1.1266% | no | no | no | yes | **retained** |
| `special_char_ratio` | shape | 1.03e-180 | +0.1787 | +0.083147 | [+0.068364, +0.097930] | 7/22 | +1.5234% | -0.2361% | no | no | yes | yes | **retained** |
| `sql_keyword_score` | signature | 9.3e-21 | +0.0421 | +0.075799 | [+0.072384, +0.079213] | 8/22 | -0.0665% | +0.0590% | no | no | yes | no | **retained** |
| `max_value_length` | lexical | 7.15e-57 | +0.0990 | +0.054690 | [+0.050146, +0.059235] | 9/22 | -0.7227% | +0.4614% | no | no | no | yes | **retained** |
| `double_escape_count` | lexical | <1e-300 | +0.1255 | +0.023479 | [+0.020406, +0.026552] | 10/22 | -0.1648% | +0.1502% | no | no | no | yes | **retained** |
| `quote_count` | lexical | <1e-300 | +0.1808 | +0.008904 | [+0.007007, +0.010800] | 11/22 | -0.0607% | +0.0805% | no | no | yes | yes | **retained** |
| `request_method_risk` | behavioral | 1.14e-09 | -0.0332 | +0.008872 | [+0.007821, +0.009922] | 12/22 | -0.7025% | +0.1448% | no | no | no | no | **retained** |
| `suspicious_extension_flag` | lexical | 2.88e-262 | +0.0625 | +0.000026 | [-0.000051, +0.000103] | 13/22 | +0.0087% | -0.0268% | no | no | yes | yes | **retained** |
| `xss_keyword_score` | signature | 6.27e-127 | +0.0305 | +0.000000 | [+0.000000, +0.000000] | 17/22 | +0.0202% | -0.0536% | no | yes | yes | no | **retained** |
| `path_traversal_score` | signature | 7.35e-36 | +0.0084 | +0.000000 | [+0.000000, +0.000000] | 17/22 | -0.0318% | +0.0161% | yes | yes | yes | no | **retained** |
| `user_agent_anomaly` | signature | 1 | +0.0000 | +0.000000 | [+0.000000, +0.000000] | 17/22 | -0.0058% | +0.0161% | yes | yes | yes | no | **retained** |
| `command_injection_score` | evasion | 7.35e-36 | +0.0084 | +0.000000 | [+0.000000, +0.000000] | 17/22 | -0.0116% | +0.0161% | yes | yes | yes | no | **retained** |
| `null_byte_score` | evasion | 1 | +0.0000 | +0.000000 | [+0.000000, +0.000000] | 17/22 | -0.0116% | -0.0215% | yes | yes | yes | no | **retained** |
| `angle_count` | lexical | 1.43e-233 | +0.0558 | +0.000000 | [+0.000000, +0.000000] | 17/22 | -0.0491% | +0.0697% | no | yes | yes | yes | **retained** |
| `token_count` | shape | 1 | -0.0415 | -0.000541 | [-0.000820, -0.000261] | 22/22 | +0.0289% | +0.0161% | yes | no | yes | yes | **retained** |

## Per-feature justification

- `param_pollution_count` is dropped: BH-adjusted p=1 with Cliff's delta=+0.0000, permutation importance +0.000000 (95% CI [+0.000000, +0.000000], rank 17/22), and leave-one-out ablation delta accuracy -0.0116% (95% CI [-0.0752%, +0.0520%]) with delta FPR -0.0215%. All four drop conditions hold.
- `html_tag_density` is dropped: BH-adjusted p=1 with Cliff's delta=+0.0000, permutation importance +0.000000 (95% CI [+0.000000, +0.000000], rank 17/22), and leave-one-out ablation delta accuracy -0.0116% (95% CI [-0.0752%, +0.0520%]) with delta FPR -0.0215%. All four drop conditions hold.
- `uppercase_ratio` is retained because at least one condition fails: C1 (univariate: p=0, delta=+0.2979); C2 (importance: mean=+0.271622, rank=1/22); C3 (ablation: delta accuracy=-1.0811%, delta FPR=+0.1448%).
- `hex_encoding_ratio` is retained because at least one condition fails: C1 (univariate: p=0, delta=+0.3861); C2 (importance: mean=+0.206935, rank=2/22); C3 (ablation: delta accuracy=-0.7169%, delta FPR=+0.4185%).
- `digit_ratio` is retained because at least one condition fails: C1 (univariate: p=7.1e-171, delta=+0.1737); C2 (importance: mean=+0.137516, rank=3/22); C3 (ablation: delta accuracy=-0.8846%, delta FPR=+0.5043%).
- `payload_length` is retained because at least one condition fails: C1 (univariate: p=3.85e-05, delta=+0.0260); C2 (importance: mean=+0.108982, rank=4/22); C3 (ablation: delta accuracy=-0.3064%, delta FPR=+0.0161%).
- `max_value_special_ratio` is retained because at least one condition fails: C1 (univariate: p=0, delta=+0.3380); C2 (importance: mean=+0.104333, rank=5/22); C3 (ablation: delta accuracy=-0.7950%, delta FPR=+0.4936%).
- `shannon_entropy` is retained because at least one condition fails: C1 (univariate: p=6.9e-76, delta=+0.1150); C2 (importance: mean=+0.093790, rank=6/22); C3 (ablation: delta accuracy=-1.5032%, delta FPR=+1.1266%).
- `special_char_ratio` is retained because at least one condition fails: C1 (univariate: p=1.03e-180, delta=+0.1787); C2 (importance: mean=+0.083147, rank=7/22).
- `sql_keyword_score` is retained by the pre-registered safety exception: it is a direct runtime policy signal, so its statistical importance does not decide whether the rule exists. Removing it from the model contract would not remove the policy rule.
- `max_value_length` is retained because at least one condition fails: C1 (univariate: p=7.15e-57, delta=+0.0990); C2 (importance: mean=+0.054690, rank=9/22); C3 (ablation: delta accuracy=-0.7227%, delta FPR=+0.4614%).
- `double_escape_count` is retained because at least one condition fails: C1 (univariate: p=0, delta=+0.1255); C2 (importance: mean=+0.023479, rank=10/22); C3 (ablation: delta accuracy=-0.1648%, delta FPR=+0.1502%).
- `quote_count` is retained because at least one condition fails: C1 (univariate: p=0, delta=+0.1808); C2 (importance: mean=+0.008904, rank=11/22).
- `request_method_risk` is retained by the pre-registered safety exception: it is a direct runtime policy signal, so its statistical importance does not decide whether the rule exists. Removing it from the model contract would not remove the policy rule.
- `suspicious_extension_flag` is retained because at least one condition fails: C1 (univariate: p=2.88e-262, delta=+0.0625); C2 (importance: mean=+0.000026, rank=13/22).
- `xss_keyword_score` is retained by the pre-registered safety exception: it is a direct runtime policy signal, so its statistical importance does not decide whether the rule exists. Removing it from the model contract would not remove the policy rule.
- `path_traversal_score` is retained by the pre-registered safety exception: it is a direct runtime policy signal, so its statistical importance does not decide whether the rule exists. Removing it from the model contract would not remove the policy rule.
- `user_agent_anomaly` is retained by the pre-registered safety exception: it is a direct runtime policy signal, so its statistical importance does not decide whether the rule exists. Removing it from the model contract would not remove the policy rule.
- `command_injection_score` is retained by the pre-registered safety exception: it is a direct runtime policy signal, so its statistical importance does not decide whether the rule exists. Removing it from the model contract would not remove the policy rule.
- `null_byte_score` is retained by the pre-registered safety exception: it is a direct runtime policy signal, so its statistical importance does not decide whether the rule exists. Removing it from the model contract would not remove the policy rule.
- `angle_count` is retained because at least one condition fails: C1 (univariate: p=1.43e-233, delta=+0.0558).
- `token_count` is retained because at least one condition fails: C2 (importance: mean=-0.000541, rank=22/22).
