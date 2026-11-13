"""Statistical helpers used by every experiment.

Deliberately small and explicit: the paper's numbers must be reproducible from
these functions without a statistics framework hiding the definition.
"""

from __future__ import annotations

import numpy as np


def bootstrap_ci(
    values,
    statistic=np.mean,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap CI for a scalar statistic."""
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    samples = statistic(arr[idx], axis=1)
    lo, hi = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def paired_bootstrap_delta(
    a,
    b,
    n_boot: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """CI for mean(a) - mean(b) using paired resampling over the same units."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n_boot, len(a)))
    deltas = a[idx].mean(axis=1) - b[idx].mean(axis=1)
    lo, hi = np.quantile(deltas, [0.025, 0.975])
    return float(lo), float(hi)


def paired_bootstrap_delta_chunked(
    a,
    b,
    n_boot: int = 2000,
    seed: int = 42,
    chunk: int = 25,
) -> tuple[float, float]:
    """Same paired bootstrap, but bounded memory.

    ``paired_bootstrap_delta`` materialises a (n_boot, n) index matrix.  At
    n=422,054 that is 6.3 GiB.  This version draws the same number of
    replicate indices in blocks; the resampling distribution is unchanged,
    only the order of the random draws differs.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    deltas = []
    for start in range(0, n_boot, chunk):
        take = min(chunk, n_boot - start)
        idx = rng.integers(0, len(a), size=(take, len(a)))
        deltas.append(a[idx].mean(axis=1) - b[idx].mean(axis=1))
    deltas = np.concatenate(deltas)
    lo, hi = np.quantile(deltas, [0.025, 0.975])
    return float(lo), float(hi)


def bh_correction(pvalues) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values."""
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted = np.empty(n)
    adjusted[order] = np.clip(ranked, 0, 1)
    return adjusted


def cliffs_delta(x, y) -> float:
    """Cliff's delta effect size in [-1, 1], positive when x tends larger."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) == 0 or len(y) == 0:
        return 0.0
    from scipy.stats import mannwhitneyu

    u = mannwhitneyu(x, y, alternative="two-sided").statistic
    return float(2.0 * u / (len(x) * len(y)) - 1.0)


def cohens_d(x, y) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return 0.0
    pooled = np.sqrt(((nx - 1) * x.var(ddof=1) + (ny - 1) * y.var(ddof=1)) / (nx + ny - 2))
    if pooled == 0:
        return 0.0
    return float((x.mean() - y.mean()) / pooled)


def mcnemar(correct_a, correct_b) -> dict:
    """McNemar test on two boolean correctness vectors."""
    a = np.asarray(correct_a, dtype=bool)
    b = np.asarray(correct_b, dtype=bool)
    n01 = int(np.sum(~a & b))
    n10 = int(np.sum(a & ~b))
    from statsmodels.stats.contingency_tables import mcnemar as sm_mcnemar

    table = [[int(np.sum(a & b)), n10], [n01, int(np.sum(~a & ~b))]]
    result = sm_mcnemar(table, exact=True)
    return {
        "n_a_only": n10,
        "n_b_only": n01,
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
    }
