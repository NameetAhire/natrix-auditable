"""Pre-registered v4 candidate features.

Every candidate is computable from the same three inputs the runtime already
passes to the extractor: the payload string (path + query + body), the
User-Agent, and the method.  That keeps the latency argument valid and makes the
definition identical across all four corpora.

Header-coherence candidates listed in protocol/feature_candidates.md are
deliberately out of scope for this cycle: the inline contract does not yet pass
raw headers, and adding them would change the runtime interface.  They are
recorded as future work.

The per-feature functions below exist so that Gate C can time each candidate
individually.  `prepare` does the shared parse once; `extract` applies every
feature function to that shared state, so the vector is identical to the
original monolithic implementation.
"""

from __future__ import annotations

import math
import types
import urllib.parse
from collections import Counter

MAX = 8192

CANDIDATE_NAMES = [
    # shape
    "url_depth",
    "query_param_count",
    "body_param_count",
    "body_to_url_ratio",
    # lexical
    "semicolon_count",
    "backslash_count",
    "brace_count",
    "dollar_count",
    "percent_ratio",
    "longest_token_length",
    "punctuation_diversity",
    "nonascii_ratio",
    # parameter semantics
    "max_param_name_entropy",
    "param_name_digit_ratio",
    "duplicate_value_count",
    "empty_value_ratio",
    # attack families
    "ldap_filter_score",
    "xpath_score",
    "ssi_directive_score",
    "nosql_operator_score",
    "template_expression_score",
    "log4shell_score",
    "crlf_sequence_count",
    "absolute_uri_in_target",
]

_DELIMS = set("&=?/ ;:,.\"'<>()[]{}|+*%\t\n\r")

_LDAP = (")(", "objectclass", "uid=", "cn=")
_XPATH = ("count(", "local-name(", "node()", "string-length(")
_SSI = ("<!--#", "#echo", "#exec", "#include")
_NOSQL = ("$ne", "$gt", "$where", "$regex")
_TEMPLATE = ("{{", "${", "<%=")
_LOG4SHELL = ("${jndi:", "ldap://", "rmi://")


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _count_any(raw: str, needles) -> int:
    return sum(raw.count(n) for n in needles)


def prepare(rec) -> types.SimpleNamespace:
    """Shared parse for all 24 candidates."""
    payload = str(rec.payload or "")[:MAX]
    lower = payload.lower()

    target, _, body = payload.partition(" ")
    path, _, query = target.partition("?")

    qpairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    bpairs = urllib.parse.parse_qsl(body, keep_blank_values=True) if body else []
    pairs = qpairs + bpairs
    names = [k for k, _ in pairs]
    values = [v for _, v in pairs]

    return types.SimpleNamespace(
        rec=rec,
        payload=payload,
        lower=lower,
        target=target,
        body=body,
        path=path,
        query=query,
        qpairs=qpairs,
        bpairs=bpairs,
        pairs=pairs,
        names=names,
        values=values,
        length=max(1, len(lower)),
    )


# ---------------------------------------------------------------------------
# Individual candidates.  Each takes the shared state and returns one float.
# ---------------------------------------------------------------------------


def url_depth(s) -> float:
    return float(s.path.count("/"))


def query_param_count(s) -> float:
    return float(len({k for k, _ in s.qpairs}))


def body_param_count(s) -> float:
    return float(len({k for k, _ in s.bpairs})) if s.body else 0.0


def body_to_url_ratio(s) -> float:
    return len(s.body) / (len(s.target) + 1)


def semicolon_count(s) -> float:
    return float(s.lower.count(";") + s.lower.count("%3b"))


def backslash_count(s) -> float:
    return float(s.lower.count("\\") + s.lower.count("%5c"))


def brace_count(s) -> float:
    return float(
        s.lower.count("{") + s.lower.count("}")
        + s.lower.count("%7b") + s.lower.count("%7d")
    )


def dollar_count(s) -> float:
    return float(s.lower.count("$") + s.lower.count("%24"))


def percent_ratio(s) -> float:
    return s.lower.count("%") / s.length


def longest_token_length(s) -> float:
    longest = 0
    run = 0
    for char in s.lower:
        if char in _DELIMS:
            if run > longest:
                longest = run
            run = 0
        else:
            run += 1
    return float(max(longest, run))


def punctuation_diversity(s) -> float:
    punct = {c for c in s.lower if not c.isalnum() and not c.isspace()}
    return len(punct) / 32.0


def nonascii_ratio(s) -> float:
    return sum(1 for c in s.lower if ord(c) > 127) / s.length


def max_param_name_entropy(s) -> float:
    return max((_entropy(k) for k in s.names), default=0.0)


def param_name_digit_ratio(s) -> float:
    name_chars = sum(len(k) for k in s.names)
    name_digits = sum(sum(ch.isdigit() for ch in k) for k in s.names)
    return name_digits / name_chars if name_chars else 0.0


def duplicate_value_count(s) -> float:
    return float(len(s.values) - len(set(s.values))) if s.values else 0.0


def empty_value_ratio(s) -> float:
    return (sum(1 for v in s.values if v == "") / len(s.values)) if s.values else 0.0


def ldap_filter_score(s) -> float:
    return float(_count_any(s.lower, _LDAP))


def xpath_score(s) -> float:
    return float(_count_any(s.lower, _XPATH))


def ssi_directive_score(s) -> float:
    return float(_count_any(s.lower, _SSI))


def nosql_operator_score(s) -> float:
    return float(_count_any(s.lower, _NOSQL))


def template_expression_score(s) -> float:
    return float(_count_any(s.lower, _TEMPLATE))


def log4shell_score(s) -> float:
    return float(_count_any(s.lower, _LOG4SHELL))


def crlf_sequence_count(s) -> float:
    return float(s.lower.count("%0d%0a") + s.lower.count("\r\n"))


def absolute_uri_in_target(s) -> float:
    return float(1 if "://" in (s.rec.url or "") else 0)


FEATURE_FUNCS = [
    url_depth,
    query_param_count,
    body_param_count,
    body_to_url_ratio,
    semicolon_count,
    backslash_count,
    brace_count,
    dollar_count,
    percent_ratio,
    longest_token_length,
    punctuation_diversity,
    nonascii_ratio,
    max_param_name_entropy,
    param_name_digit_ratio,
    duplicate_value_count,
    empty_value_ratio,
    ldap_filter_score,
    xpath_score,
    ssi_directive_score,
    nosql_operator_score,
    template_expression_score,
    log4shell_score,
    crlf_sequence_count,
    absolute_uri_in_target,
]

assert [fn.__name__ for fn in FEATURE_FUNCS] == CANDIDATE_NAMES


def extract(rec) -> list[float]:
    state = prepare(rec)
    return [fn(state) for fn in FEATURE_FUNCS]
