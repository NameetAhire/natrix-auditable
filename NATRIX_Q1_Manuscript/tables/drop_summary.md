# Feature-drop outcome (summary)

| feature | group | p (BH) | Cliff delta | permutation importance | 95% CI | rank | decision |
|---|---|---:|---:|---:|---|---:|---|
| `param_pollution_count` | structural | 1 | +0.0000 | +0.000000 | [+0.000000, +0.000000] | 17/22 | dropped |
| `html_tag_density` | structural | 1 | +0.0000 | +0.000000 | [+0.000000, +0.000000] | 17/22 | dropped |
| `token_count` | shape | 1 | -0.0415 | -0.000541 | [-0.000820, -0.000261] | 22/22 | retained |

C1 is the Benjamini-Hochberg univariate screen (null or near-constant),
C2 the permutation-importance screen (bottom quartile and interval containing
zero), C3 the leave-one-feature-out ablation (within the practical-equivalence
margin), and C4 the pre-registered safety exception. The two dropped features
are exactly zero on CSIC in both classes. `token_count` is retained because its
permutation interval is strictly negative rather than containing zero; the
retention is a documented cost of the frozen rule, not evidence that the
feature is useful. The repository tables give the C1-C4 columns and the ablation values.
