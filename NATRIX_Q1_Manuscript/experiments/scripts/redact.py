"""Redact credential-like values from the public latency inputs.

This is a release sanitizer, not a general DLP scanner: it covers the common
URL, form and JSON parameter names plus the token shapes seen in the WCP
corpus. Values are replaced with same-length ``~`` placeholders so request
structure and length are preserved.

shortcut: only known parameter names and token shapes are redacted; extend the
patterns if a new corpus introduces another credential format.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

SENSITIVE_WORDS = (
    r"token|key|secret|sig|signature|password|pwd|auth|session|csrf|"
    r"xsrf|credential|assertion"
)

SENSITIVE = re.compile(rf"(?i)(?:{SENSITIVE_WORDS})")

PARAM = re.compile(r"(?i)(^|[?&;])([^=?&#;]+)=([^?&#;]*)")
JSON_PAIR = re.compile(
    rf'(?i)("([^"]*(?:{SENSITIVE_WORDS})[^"]*)"\s*:\s*")([^"]*)(")'
)
KNOWN = (
    (re.compile(r"AKIA[0-9A-Z]{16}"), lambda m: "~" * len(m.group(0))),
    (
        re.compile(r"(?:pk|sk)\.[A-Za-z0-9_\-\.]{20,}"),
        lambda m: "~" * len(m.group(0)),
    ),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), lambda m: "~" * len(m.group(0))),
)


def _mask(value: str) -> str:
    return "~" * len(value)


def redact_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    for pattern, replacement in KNOWN:
        text = pattern.sub(replacement, text)
    text = JSON_PAIR.sub(
        lambda m: m.group(1) + _mask(m.group(3)) + m.group(4), text
    )

    def replace_param(match: re.Match) -> str:
        name = match.group(2)
        if SENSITIVE.search(unquote(name)):
            return match.group(1) + name + "=" + _mask(match.group(3))
        return match.group(0)

    return PARAM.sub(replace_param, text)


def redact_item(item: dict) -> dict:
    out = dict(item)
    for field in ("url", "body"):
        if field in out:
            out[field] = redact_text(out[field])
    return out


if __name__ == "__main__":
    _cases = [
        "/x?apiKey=abc123",
        "/p?Action=GetEditorsTable&access_token=abc123",
        '{"query":"cart($id:ID)=x?key=abc123"}',
        "/k?X-Amz-Credential=AKIAABCDEFGHIJKLMNOP",
        "/e?access_token=pk.abcdefghijklmnopqrstuvwxyz",
    ]
    for _case in _cases:
        _out = redact_text(_case)
        assert len(_out) == len(_case), (_case, _out)
        assert "abc123" not in _out and "AKIA" not in _out and "pk." not in _out
    assert "Action=GetEditorsTable" in redact_text(_cases[1])
    print("redact self-check passed")
