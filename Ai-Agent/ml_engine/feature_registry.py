"""
═══════════════════════════════════════════════════════════════════════════════
NATRIX ADAPTIVE SECURITY — EXTENSIBLE FEATURE REGISTRY (feature_registry.py)
Supports dynamic expansion from 10 baseline features (v1) to 16 enhanced features
(v2) and 22 measured features (v3) without breaking existing production models or
dropping requests.

The v2 and v3 contracts are mirrored in proxy/feature_extractor.js.  Any change to
a formula here MUST be made in both files and covered by
tests/feature_parity_cases.json.
═══════════════════════════════════════════════════════════════════════════════
"""

import math
import re
import json
import os
import urllib.parse
from collections import Counter

# Hard cap on the number of code points inspected per request.  An 8 KiB
# inspection window bounds the worst-case extraction cost (all scans are
# linear) while comfortably covering URLs and the security-relevant prefix of
# request bodies; measured at-cap cost is ~1.4 ms in Node and ~3.5 ms in
# CPython, both inside the 5 ms budget even on a loaded developer machine.
MAX_PAYLOAD_CHARS = 8192

# Known malicious scanner user-agent keywords
KNOWN_SCANNER_UAS = [
    'sqlmap', 'nikto', 'nmap', 'masscan', 'gobuster', 'dirbuster',
    'w3af', 'acunetix', 'havij', 'hydra', 'metasploit', 'botnet', 'zgrab',
    'wpscan', 'censys', 'shodan'
]

# Security keywords
SQL_KEYWORDS = [
    'select', 'union', 'drop', 'insert', 'delete', 'update', 'where',
    'or 1=1', '--', 'information_schema', 'sleep(', 'benchmark(',
]
XSS_KEYWORDS = [
    '<script>', 'javascript:', 'onerror=', 'onload=', 'eval(', 'alert(',
    'document.cookie', '<iframe', '<svg',
]
TRAVERSAL_KEYWORDS = ['../', '..\\', '/etc/passwd', 'c:\\windows', 'boot.ini', '/proc/self']

# Command injection is deliberately pattern-based rather than a bag of shell
# separators.  Counting every ';' or '|' would flag ordinary prose and JSON,
# so a separator only scores when it is followed by a known command token.
CMD_PATTERNS = [
    re.compile(
        r'(?:;|\|\||&&|\|)\s*'
        r'(?:cat|ls|id|whoami|uname|pwd|curl|wget|nc|netcat|bash|sh|zsh|'
        r'powershell|pwsh|cmd(?:\.exe)?|python|perl|rm|chmod|chown|kill|'
        r'ps|ifconfig|ipconfig)\b',
        re.IGNORECASE,
    ),
    re.compile(r'(?:/bin/(?:sh|bash)|\bcmd\.exe\b|\bpowershell\b|\bpwsh\b)', re.IGNORECASE),
    re.compile(r'\b(?:cat|type)\s+/etc/', re.IGNORECASE),
    re.compile(r'\b(?:curl|wget)\s+https?://', re.IGNORECASE),
    re.compile(r'\bnc\s+-e\b', re.IGNORECASE),
    # Require a known command token inside substitutions so Markdown/backticks
    # in ordinary prose do not look like remote code execution.  The closing
    # delimiter is intentionally not required: scanning to it was quadratic on
    # hostile input ("$(cat$(cat..."), while an unclosed substitution is if
    # anything more suspicious.
    re.compile(
        r'\$\(\s*(?:cat|ls|id|whoami|uname|pwd|curl|wget|nc|netcat|bash|sh|zsh|'
        r'powershell|pwsh|python|perl|rm|chmod|chown|kill|ps|ifconfig|ipconfig)\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'`\s*(?:cat|ls|id|whoami|uname|pwd|curl|wget|nc|netcat|bash|sh|zsh|'
        r'powershell|pwsh|python|perl|rm|chmod|chown|kill|ps|ifconfig|ipconfig)\b',
        re.IGNORECASE,
    ),
]

# Each command regex is preceded by a cheap substring check for a literal the
# pattern cannot match without.  Benign payloads (long tokens, JSON bodies)
# skip seven full scans; the detected set is unchanged because every literal is
# a necessary condition of its pattern.
CMD_PREFILTERS = [
    (';', '|', '&'),                    # separators
    ('/bin/', 'cmd.exe', 'powershell', 'pwsh'),
    ('/etc/',),
    ('curl', 'wget'),
    ('-e',),
    ('$(',),
    ('`',),
]

# A tag starts with '<', optional whitespace and a name.  The first '>' after
# the name closes it because [^>]* cannot consume one; _count_open_tags() walks
# that in linear time.  The equivalent findall() regex rescan suffered
# quadratic behaviour on payloads such as "<a<a<a..." with no closing '>'.
TAG_OPEN_PATTERN = re.compile(r'<\s*[a-zA-Z][a-zA-Z0-9:-]*')
HEX_PATTERN = re.compile(r'(%[0-9a-fA-F]{2}|\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4})')
NULL_BYTE_PATTERN = re.compile(r'(%00|\\x00|\\0|\x00)')

# Keys are matched from the start of a run only.  The natural regex
# ([a-zA-Z0-9_.-]+)= retries the whole run from every position when no '='
# follows, which is quadratic on long tokens (JWTs, base64 blobs, hashes).
# The negative lookbehind makes each run inspected once, so the scan is linear.
PARAM_KEY_PATTERN = re.compile(r'(?<![a-zA-Z0-9_.-])([a-zA-Z0-9_.-]+)=')

METHOD_RISK_WEIGHTS = {
    'GET': 0.1,
    'POST': 0.4,
    'PUT': 0.6,
    'DELETE': 0.6,
    'PATCH': 0.5,
    'OPTIONS': 0.2,
    'HEAD': 0.1,
    'TRACE': 1.0,  # TRACE enables cross-site tracing (XST)
    'CONNECT': 0.8,
}

# Extensions that should never be publicly served.  Kept generic (no
# CSIC-specific names) so the feature transfers to other HTTP corpora.
SUSPICIOUS_EXTENSIONS = (
    '.bak', '.old', '.inc', '.config', '.env', '.git', '.svn', '.sql',
    '.zip', '.tar', '.gz', '.log', '.ini', '.swp', '.php~', '.orig', '.save',
)

DOUBLE_ESCAPE_PATTERN = re.compile(r'%25[0-9a-fA-F]{2}')

# ─── Feature documentation (used by the schema manifest and the viva notes) ───
FEATURE_GROUPS = {
    'shape': [
        'payload_length', 'shannon_entropy', 'special_char_ratio',
        'digit_ratio', 'uppercase_ratio', 'token_count',
    ],
    'signature': [
        'sql_keyword_score', 'xss_keyword_score',
        'path_traversal_score', 'user_agent_anomaly',
    ],
    'evasion': ['command_injection_score', 'hex_encoding_ratio', 'null_byte_score'],
    'structural': ['param_pollution_count', 'html_tag_density'],
    'behavioral': ['request_method_risk'],
    'lexical': [
        'suspicious_extension_flag', 'quote_count', 'angle_count',
        'double_escape_count', 'max_value_special_ratio', 'max_value_length',
    ],
}

FEATURE_DESCRIPTIONS = {
    'payload_length': 'Total characters in URL path + query string + request body.',
    'shannon_entropy': 'Shannon entropy of the payload; high values indicate encoded or random content.',
    'special_char_ratio': 'Fraction of non-alphanumeric, non-whitespace characters.',
    'digit_ratio': 'Fraction of numeric characters (hex/ASCII encoding signal).',
    'uppercase_ratio': 'Fraction of uppercase ASCII letters (keyword-style SQL signal).',
    'token_count': 'Number of whitespace-delimited lexical tokens.',
    'sql_keyword_score': 'Number of distinct SQL-injection keywords present.',
    'xss_keyword_score': 'Number of distinct XSS/script-injection keywords present.',
    'path_traversal_score': 'Number of distinct directory-traversal patterns present.',
    'user_agent_anomaly': '1 when the User-Agent names a known attack scanner, else 0.',
    'command_injection_score': 'Number of shell/RCE command-injection patterns present.',
    'hex_encoding_ratio': 'Fraction of payload characters consumed by %XX, \\xXX or \\uXXXX escapes.',
    'null_byte_score': '1 when a literal or encoded null byte is present, else 0.',
    'param_pollution_count': 'Number of duplicated parameter keys (HTTP parameter pollution).',
    'html_tag_density': 'Opening HTML/XML/SVG tags per whitespace token.',
    'request_method_risk': 'Risk weight of the HTTP verb (GET 0.1 ... TRACE 1.0).',
    'suspicious_extension_flag': '1 when the path ends in a backup/config/source extension, else 0.',
    'quote_count': 'Total single/double quote characters, raw or percent-encoded.',
    'angle_count': 'Total angle-bracket characters, raw or percent-encoded.',
    'double_escape_count': 'Number of %25XX double-encoded sequences (evasion signal).',
    'max_value_special_ratio': 'Highest non-alphanumeric, non-space ratio among parameter values.',
    'max_value_length': 'Length of the longest query or form parameter value.',
}


def _round4(value: float) -> float:
    """Round half-up, matching proxy/feature_extractor.js exactly.

    Python's built-in round() uses banker's rounding, which can disagree with
    JavaScript's Math.round() on exact .00005 boundaries.  Parity fixtures
    compare exact floats, so both implementations use the same quantizer.
    """
    return math.floor(value * 10000 + 0.5) / 10000


def _entropy_from_frequency(frequency: Counter, length: int) -> float:
    if length <= 0:
        return 0.0
    entropy = 0.0
    for count in frequency.values():
        p = count / length
        entropy -= p * math.log2(p)
    return _round4(entropy)


def calculate_shannon_entropy(text: str) -> float:
    """Calculates Shannon Entropy of a string to detect encrypted or obfuscated payloads."""
    if not text:
        return 0.0
    return _entropy_from_frequency(Counter(text), len(text))


def _is_ascii_alnum_or_space(char: str) -> bool:
    """Twin of [a-zA-Z0-9\\s] for a single code point."""
    return (
        'a' <= char <= 'z'
        or 'A' <= char <= 'Z'
        or '0' <= char <= '9'
        or char.isspace()
    )


def _count_duplicate_param_keys(text: str) -> int:
    """Count duplicated ``key=`` pairs without quadratic rescanning.

    Semantically identical to the original ``([a-zA-Z0-9_.-]+)=`` findall:
    the negative lookbehind only suppresses retries that would start inside an
    already-scanned run, so each run is inspected once on hostile input.
    """
    keys = PARAM_KEY_PATTERN.findall(text)
    return len(keys) - len(set(keys)) if keys else 0


def _command_injection_score(combined_payload: str) -> int:
    """Count matching command-injection patterns behind cheap prefilters."""
    score = 0
    for literals, pattern in zip(CMD_PREFILTERS, CMD_PATTERNS):
        if not any(literal in combined_payload for literal in literals):
            continue
        if pattern.search(combined_payload):
            score += 1
    return score


def _iter_parameter_values(payload: str) -> list:
    """Return decoded query/form parameter values in wire order.

    The runtime payload is ``path?query body``.  Query and form bodies are
    parsed with ``parse_qsl`` so duplicate keys and blank values are preserved,
    matching the CSIC evaluation's ``parse_qs(..., keep_blank_values=True)``.
    JSON bodies do not have ``key=value`` fields; they yield no useful values,
    which is intentional: the six v3 features are HTTP form/query signals.
    """
    target, _, body = payload.partition(' ')
    query = target.split('?', 1)[1] if '?' in target else ''
    values = []
    for text in (query, body):
        if text:
            values.extend(value for _key, value in urllib.parse.parse_qsl(text, keep_blank_values=True))
    return values


def _max_value_features(values: list) -> tuple:
    """Return (max special-char ratio, max value length), rounded for parity."""
    if not values:
        return 0.0, 0
    max_special = 0.0
    max_length = 0
    for value in values:
        length = len(value)
        if length > max_length:
            max_length = length
        if length:
            special = sum(1 for char in value if not char.isalnum() and not char.isspace())
            ratio = special / length
            if ratio > max_special:
                max_special = ratio
    return _round4(max_special), max_length


def _lexical_features(payload: str) -> dict:
    """The six generic v3 lexical/shape features."""
    target = payload.partition(' ')[0]
    path = target.split('?', 1)[0].lower()
    raw = payload.lower()
    values = _iter_parameter_values(payload)
    max_special, max_value_length = _max_value_features(values)
    return {
        'suspicious_extension_flag': 1 if path.endswith(SUSPICIOUS_EXTENSIONS) else 0,
        'quote_count': raw.count("'") + raw.count('"') + raw.count('%27') + raw.count('%22'),
        'angle_count': raw.count('<') + raw.count('>') + raw.count('%3c') + raw.count('%3e'),
        'double_escape_count': len(DOUBLE_ESCAPE_PATTERN.findall(raw)),
        'max_value_special_ratio': max_special,
        'max_value_length': max_value_length,
    }


def _count_open_tags(text: str) -> int:
    """Count opening HTML/XML/SVG tags in linear time.

    Semantically identical to ``re.findall(r'<\\s*[a-zA-Z][a-zA-Z0-9:-]*[^>]*>')``:
    a tag runs from '<' to the first following '>', matches are non-overlapping,
    and closing tags are not counted.  ``finditer`` scans in C; the monotonic
    '>' cursor prevents the repeated end-of-string rescans that made the naive
    findall quadratic on inputs such as ">" + "<a" * n.
    """
    count = 0
    consumed = -1
    closing = text.find('>')
    for opening in TAG_OPEN_PATTERN.finditer(text):
        if opening.start() < consumed:
            continue
        if closing < opening.end():
            closing = text.find('>', opening.end())
        if closing == -1:
            break
        count += 1
        consumed = closing + 1
    return count


class FeatureRegistry:
    """
    Central registry for security feature extractors with schema versioning.
    Allows zero-downtime hot-swapping between v1 (10), v2 (16) and v3 (22).
    """

    def __init__(self):
        # Ordered feature definitions for v1 (10 features)
        self.v1_features = [
            "payload_length",
            "shannon_entropy",
            "special_char_ratio",
            "digit_ratio",
            "uppercase_ratio",
            "token_count",
            "sql_keyword_score",
            "xss_keyword_score",
            "path_traversal_score",
            "user_agent_anomaly",
        ]

        # Ordered feature definitions for v2 (16 features)
        self.v2_features = list(self.v1_features) + [
            "command_injection_score",
            "hex_encoding_ratio",
            "null_byte_score",
            "param_pollution_count",
            "html_tag_density",
            "request_method_risk",
        ]

        # Ordered feature definitions for v3 (22 features).  The extra six are
        # generic lexical/shape signals, validated on CSIC 2010.
        self.v3_features = list(self.v2_features) + [
            "suspicious_extension_flag",
            "quote_count",
            "angle_count",
            "double_escape_count",
            "max_value_special_ratio",
            "max_value_length",
        ]

    def get_feature_names(self, version: str = "v3") -> list:
        if version == "v1":
            return list(self.v1_features)
        if version == "v2":
            return list(self.v2_features)
        return list(self.v3_features)

    def get_feature_groups(self) -> dict:
        return {name: list(features) for name, features in FEATURE_GROUPS.items()}

    def get_feature_descriptions(self) -> dict:
        return dict(FEATURE_DESCRIPTIONS)

    def extract_features(self, payload: str, user_agent: str = "", method: str = "GET", version: str = "v3") -> dict:
        """
        Extracts numerical security features from request payload + user agent + method.
        Supports version='v1' (10), version='v2' (16) and version='v3' (22).
        """
        payload_str = str(payload or "")[:MAX_PAYLOAD_CHARS]
        ua_str = str(user_agent or "").lower()
        method_str = str(method or "GET").upper()
        length = len(payload_str)
        lower_payload = payload_str.lower()
        decoded_payload = urllib.parse.unquote(payload_str).lower()
        combined_payload = lower_payload + " " + decoded_payload
        tokens = payload_str.split()

        # ─── Baseline 10 Features (v1) ───
        # One C-speed character count feeds entropy and all three ratio
        # features; the previous implementation ran three regex substitutions
        # plus a per-character dict loop over every request.
        frequency = Counter(payload_str)
        special_chars = 0
        digit_chars = 0
        uppercase_chars = 0
        for char, count in frequency.items():
            if not _is_ascii_alnum_or_space(char):
                special_chars += count
            if '0' <= char <= '9':
                digit_chars += count
            elif 'A' <= char <= 'Z':
                uppercase_chars += count

        features = {
            "payload_length": length,
            "shannon_entropy": _entropy_from_frequency(frequency, length),
            "special_char_ratio": _round4(special_chars / length) if length else 0.0,
            "digit_ratio": _round4(digit_chars / length) if length else 0.0,
            "uppercase_ratio": _round4(uppercase_chars / length) if length else 0.0,
            "token_count": len(tokens),
            "sql_keyword_score": sum(1 for kw in SQL_KEYWORDS if kw in combined_payload),
            "xss_keyword_score": sum(1 for kw in XSS_KEYWORDS if kw in combined_payload),
            "path_traversal_score": sum(1 for kw in TRAVERSAL_KEYWORDS if kw in combined_payload),
            "user_agent_anomaly": 1 if any(scanner in ua_str for scanner in KNOWN_SCANNER_UAS) else 0,
        }

        # If only v1 requested, return the 10 features
        if version == "v1":
            return features

        # ─── Enhanced 6 Features (v2 Expansion) ───
        # 11. Command Injection Score (checked against both raw and URL-decoded payload)
        cmd_score = _command_injection_score(combined_payload)

        # 12. Hex / Percent-Encoding Ratio (evasion detection)
        # Count the characters consumed by each escape, not the number of escapes.
        hex_chars = sum(len(match.group(0)) for match in HEX_PATTERN.finditer(payload_str))
        hex_ratio = _round4(hex_chars / max(1, length))

        # 13. Null Byte Poisoning Score (bypasses file extensions like .php%00.jpg)
        null_byte_score = 1 if NULL_BYTE_PATTERN.search(payload_str) else 0

        # 14. Parameter Pollution / Repetition count
        param_pollution_count = _count_duplicate_param_keys(payload_str)

        # 15. HTML/XML/SVG Tag Density
        html_tag_density = _round4(_count_open_tags(payload_str) / max(1, len(tokens)))

        # 16. Request Method Risk
        method_risk = METHOD_RISK_WEIGHTS.get(method_str, 0.5)

        features.update({
            "command_injection_score": cmd_score,
            "hex_encoding_ratio": hex_ratio,
            "null_byte_score": null_byte_score,
            "param_pollution_count": param_pollution_count,
            "html_tag_density": html_tag_density,
            "request_method_risk": method_risk,
        })

        if version == "v2":
            return features

        # ─── Lexical 6 Features (v3 Expansion) ───
        features.update(_lexical_features(payload_str))
        return features

    def feature_dict_to_vector(self, features: dict, version: str = "v3") -> list:
        """Converts feature dictionary into an ordered numerical array for scikit-learn / XGBoost."""
        names = self.get_feature_names(version)
        return [features.get(name, 0) for name in names]

    def export_manifest(self, filepath: str = "models/feature_schema.json"):
        """Exports the active feature schema manifest to disk for CI/CD and synchronization."""
        manifest = {
            "v1": {
                "count": len(self.v1_features),
                "features": self.v1_features,
            },
            "v2": {
                "count": len(self.v2_features),
                "features": self.v2_features,
                "groups": self.get_feature_groups(),
                "descriptions": self.get_feature_descriptions(),
            },
            "v3": {
                "count": len(self.v3_features),
                "features": self.v3_features,
                "groups": self.get_feature_groups(),
                "descriptions": self.get_feature_descriptions(),
            },
            "default_version": "v3",
            "supported_versions": ["v1", "v2", "v3"],
        }
        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        return manifest


# Singleton instance
registry = FeatureRegistry()
