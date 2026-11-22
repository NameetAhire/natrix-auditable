'use strict';

/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * NATRIX 22-D FEATURE EXTRACTOR (proxy/feature_extractor.js)
 *
 * This is the JavaScript twin of ml_engine/feature_registry.py.  The proxy needs
 * the same vector locally for two reasons:
 *   1. The inline path must not depend on a Python HTTP round-trip.
 *   2. Every blocked/analysed request can be audited with its exact vector.
 *
 * Keep the order and formulas byte-for-byte aligned with the Python registry.
 * tests/feature_parity_cases.json is the cross-language contract.
 * ═══════════════════════════════════════════════════════════════════════════════
 */

const V2_FEATURE_NAMES = Object.freeze([
  'payload_length',
  'shannon_entropy',
  'special_char_ratio',
  'digit_ratio',
  'uppercase_ratio',
  'token_count',
  'sql_keyword_score',
  'xss_keyword_score',
  'path_traversal_score',
  'user_agent_anomaly',
  'command_injection_score',
  'hex_encoding_ratio',
  'null_byte_score',
  'param_pollution_count',
  'html_tag_density',
  'request_method_risk',
]);

const V3_FEATURE_NAMES = Object.freeze([
  ...V2_FEATURE_NAMES,
  'suspicious_extension_flag',
  'quote_count',
  'angle_count',
  'double_escape_count',
  'max_value_special_ratio',
  'max_value_length',
]);

// The active contract.  V1/V2 remain available for old callers and models.
const FEATURE_NAMES = V3_FEATURE_NAMES;
const V1_FEATURE_NAMES = Object.freeze(V2_FEATURE_NAMES.slice(0, 10));

// Mirrors MAX_PAYLOAD_CHARS in ml_engine/feature_registry.py.  An 8 KiB
// inspection window bounds the worst-case extraction cost (all scans are
// linear) while comfortably covering URLs and the security-relevant prefix of
// request bodies; measured at-cap cost is ~1.4 ms in Node and ~3.5 ms in
// CPython, both inside the 5 ms budget even on a loaded developer machine.
const MAX_PAYLOAD_CHARS = 8192;

const FEATURE_GROUPS = Object.freeze({
  shape: Object.freeze(['payload_length', 'shannon_entropy', 'special_char_ratio', 'digit_ratio', 'uppercase_ratio', 'token_count']),
  signature: Object.freeze(['sql_keyword_score', 'xss_keyword_score', 'path_traversal_score', 'user_agent_anomaly']),
  evasion: Object.freeze(['command_injection_score', 'hex_encoding_ratio', 'null_byte_score']),
  structural: Object.freeze(['param_pollution_count', 'html_tag_density']),
  behavioral: Object.freeze(['request_method_risk']),
  lexical: Object.freeze([
    'suspicious_extension_flag', 'quote_count', 'angle_count',
    'double_escape_count', 'max_value_special_ratio', 'max_value_length',
  ]),
});

const FEATURE_DESCRIPTIONS = Object.freeze({
  payload_length: 'Total characters in URL path + query string + request body.',
  shannon_entropy: 'Shannon entropy of the payload; high values indicate encoded or random content.',
  special_char_ratio: 'Fraction of non-alphanumeric, non-whitespace characters.',
  digit_ratio: 'Fraction of numeric characters (hex/ASCII encoding signal).',
  uppercase_ratio: 'Fraction of uppercase ASCII letters (keyword-style SQL signal).',
  token_count: 'Number of whitespace-delimited lexical tokens.',
  sql_keyword_score: 'Number of distinct SQL-injection keywords present.',
  xss_keyword_score: 'Number of distinct XSS/script-injection keywords present.',
  path_traversal_score: 'Number of distinct directory-traversal patterns present.',
  user_agent_anomaly: '1 when the User-Agent names a known attack scanner, else 0.',
  command_injection_score: 'Number of shell/RCE command-injection patterns present.',
  hex_encoding_ratio: 'Fraction of payload characters consumed by %XX, \\xXX or \\uXXXX escapes.',
  null_byte_score: '1 when a literal or encoded null byte is present, else 0.',
  param_pollution_count: 'Number of duplicated parameter keys (HTTP parameter pollution).',
  html_tag_density: 'Opening HTML/XML/SVG tags per whitespace token.',
  request_method_risk: 'Risk weight of the HTTP verb (GET 0.1 ... TRACE 1.0).',
  suspicious_extension_flag: '1 when the path ends in a backup/config/source extension, else 0.',
  quote_count: 'Total single/double quote characters, raw or percent-encoded.',
  angle_count: 'Total angle-bracket characters, raw or percent-encoded.',
  double_escape_count: 'Number of %25XX double-encoded sequences (evasion signal).',
  max_value_special_ratio: 'Highest non-alphanumeric, non-space ratio among parameter values.',
  max_value_length: 'Length of the longest query or form parameter value.',
});

const KNOWN_SCANNER_UAS = Object.freeze([
  'sqlmap', 'nikto', 'nmap', 'masscan', 'gobuster', 'dirbuster',
  'w3af', 'acunetix', 'havij', 'hydra', 'metasploit', 'botnet', 'zgrab',
  'wpscan', 'censys', 'shodan',
]);

const SQL_KEYWORDS = Object.freeze([
  'select', 'union', 'drop', 'insert', 'delete', 'update', 'where',
  'or 1=1', '--', 'information_schema', 'sleep(', 'benchmark(',
]);

const XSS_KEYWORDS = Object.freeze([
  '<script>', 'javascript:', 'onerror=', 'onload=', 'eval(', 'alert(',
  'document.cookie', '<iframe', '<svg',
]);

const TRAVERSAL_KEYWORDS = Object.freeze(['../', '..\\', '/etc/passwd', 'c:\\windows', 'boot.ini', '/proc/self']);

const CMD_PATTERNS = Object.freeze([
  /(?:;|\|\||&&|\|)\s*(?:cat|ls|id|whoami|uname|pwd|curl|wget|nc|netcat|bash|sh|zsh|powershell|pwsh|cmd(?:\.exe)?|python|perl|rm|chmod|chown|kill|ps|ifconfig|ipconfig)\b/i,
  /(?:[/]bin[/](?:sh|bash)|\bcmd\.exe\b|\bpowershell\b|\bpwsh\b)/i,
  /\b(?:cat|type)\s+\/etc\//i,
  /\b(?:curl|wget)\s+https?:\/\//i,
  /\bnc\s+-e\b/i,
  // Require a known command token inside substitutions so Markdown/backticks
  // in ordinary prose do not look like remote code execution.  The closing
  // delimiter is intentionally not required: scanning to it was quadratic on
  // hostile input ("$(cat$(cat..."), while an unclosed substitution is if
  // anything more suspicious.
  /\$\(\s*(?:cat|ls|id|whoami|uname|pwd|curl|wget|nc|netcat|bash|sh|zsh|powershell|pwsh|python|perl|rm|chmod|chown|kill|ps|ifconfig|ipconfig)\b/i,
  /`\s*(?:cat|ls|id|whoami|uname|pwd|curl|wget|nc|netcat|bash|sh|zsh|powershell|pwsh|python|perl|rm|chmod|chown|kill|ps|ifconfig|ipconfig)\b/i,
]);

// Each command regex is preceded by a cheap substring check for a literal the
// pattern cannot match without.  Benign payloads (long tokens, JSON bodies)
// skip seven full scans; the detected set is unchanged because every literal is
// a necessary condition of its pattern.
const CMD_PREFILTERS = Object.freeze([
  Object.freeze([';', '|', '&']),                     // separators
  Object.freeze(['/bin/', 'cmd.exe', 'powershell', 'pwsh']),
  Object.freeze(['/etc/']),
  Object.freeze(['curl', 'wget']),
  Object.freeze(['-e']),
  Object.freeze(['$(']),
  Object.freeze(['`']),
]);

const HEX_PATTERN = /(%[0-9a-fA-F]{2}|\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4})/g;
const NULL_BYTE_PATTERN = /(%00|\\x00|\\0|\x00)/;

// Keys are matched from the start of a run only.  The natural regex
// ([a-zA-Z0-9_.-]+)= retries the whole run from every position when no '='
// follows, which is quadratic on long tokens (JWTs, base64 blobs, hashes).
// The negative lookbehind makes each run inspected once, so the scan is linear.
const PARAM_KEY_PATTERN = /(?<![a-zA-Z0-9_.-])([a-zA-Z0-9_.-]+)=/g;

const METHOD_RISK_WEIGHTS = Object.freeze({
  GET: 0.1,
  POST: 0.4,
  PUT: 0.6,
  DELETE: 0.6,
  PATCH: 0.5,
  OPTIONS: 0.2,
  HEAD: 0.1,
  TRACE: 1.0,
  CONNECT: 0.8,
});

// A conservative safety net that combines weak signals.  Individual known
// attacks are still caught by the explicit regex rules; this score only blocks
// when several independent dimensions agree.  It keeps the 16 features useful
// even when the optional Python ML service is disabled or unreachable.
const SUSPICIOUS_EXTENSIONS = Object.freeze([
  '.bak', '.old', '.inc', '.config', '.env', '.git', '.svn', '.sql',
  '.zip', '.tar', '.gz', '.log', '.ini', '.swp', '.php~', '.orig', '.save',
]);

const DOUBLE_ESCAPE_PATTERN = /%25[0-9a-fA-F]{2}/g;

const FEATURE_RISK_THRESHOLD = 0.6;

// Python 3 len() counts Unicode code points, whereas JavaScript String.length
// counts UTF-16 code units.  All length-derived features use code points so
// that the two implementations agree on non-BMP payloads.
function codePointLength(value) {
  let count = 0;
  for (const _ of value) count++;
  return count;
}

// Python slices strings by code point; String.slice() uses UTF-16 units.
function sliceCodePoints(value, max) {
  if (value.length <= max) return value;
  let count = 0;
  let end = 0;
  for (const char of value) {
    if (count >= max) break;
    count++;
    end += char.length;
  }
  return value.slice(0, end);
}

// Math.round() rounds half away from zero for positive values, matching the
// Python _round4() helper (floor(x * 10000 + 0.5) / 10000).
function round4(value) {
  return Math.round(value * 10000) / 10000;
}

function calculateShannonEntropy(text) {
  if (!text) return 0;
  const freq = new Map();
  let length = 0;
  for (const char of text) {
    freq.set(char, (freq.get(char) || 0) + 1);
    length++;
  }
  if (length === 0) return 0;
  let entropy = 0;
  for (const count of freq.values()) {
    const p = count / length;
    entropy -= p * Math.log2(p);
  }
  return round4(entropy);
}

function isAsciiHexByte(byte) {
  return (byte >= 0x30 && byte <= 0x39) || (byte >= 0x41 && byte <= 0x46) || (byte >= 0x61 && byte <= 0x66);
}

/**
 * Exact twin of urllib.parse.unquote(payload, encoding='utf-8', errors='replace').
 * decodeURIComponent() throws on malformed escapes and decodes reserved
 * characters identically, but Python replaces invalid bytes instead of
 * throwing.  Decoding the UTF-8 byte stream ourselves keeps hostile payloads
 * (e.g. "%E0%A4%A") from producing language-dependent feature vectors.
 */
function pythonUnquote(value) {
  if (!value.includes('%')) return value;
  const input = Buffer.from(value, 'utf8');
  const output = Buffer.allocUnsafe(input.length);
  let written = 0;
  for (let i = 0; i < input.length; i++) {
    const byte = input[i];
    if (byte === 0x25 && i + 2 < input.length && isAsciiHexByte(input[i + 1]) && isAsciiHexByte(input[i + 2])) {
      const hex = String.fromCharCode(input[i + 1], input[i + 2]);
      output[written++] = parseInt(hex, 16);
      i += 2;
    } else {
      output[written++] = byte;
    }
  }
  return new TextDecoder('utf-8', { fatal: false }).decode(output.subarray(0, written));
}

function countKeywordHits(haystack, keywords) {
  let hits = 0;
  for (const keyword of keywords) {
    if (haystack.includes(keyword)) hits++;
  }
  return hits;
}

function commandInjectionScore(combinedPayload) {
  let score = 0;
  for (let index = 0; index < CMD_PATTERNS.length; index++) {
    const literals = CMD_PREFILTERS[index];
    if (!literals.some((literal) => combinedPayload.includes(literal))) continue;
    if (CMD_PATTERNS[index].test(combinedPayload)) score++;
  }
  return score;
}

function hexEncodingRatio(payload, payloadLength) {
  const matches = payload.match(HEX_PATTERN);
  if (!matches) return 0;
  let encodedChars = 0;
  for (const match of matches) encodedChars += match.length;
  return round4(encodedChars / Math.max(1, payloadLength));
}

function paramPollutionCount(payload) {
  const matches = payload.match(PARAM_KEY_PATTERN);
  if (!matches) return 0;
  const keys = matches.map((entry) => entry.slice(0, -1));
  return keys.length - new Set(keys).size;
}

// Global scan used by countOpenTags(); lastIndex is reset per call.
// ASCII-only on purpose: the i flag makes Python match four exotic Unicode
// letters that V8 does not, which would break cross-language parity.
const TAG_OPEN_SCAN = /<\s*[a-zA-Z][a-zA-Z0-9:-]*/g;

// Mirrors Python _count_open_tags(): a tag runs from '<' to the first following
// '>', matches are non-overlapping, closing tags are not counted, and the
// monotonic '>' cursor keeps hostile input linear.
function countOpenTags(payload) {
  let count = 0;
  let consumed = -1;
  let closing = payload.indexOf('>');
  TAG_OPEN_SCAN.lastIndex = 0;
  let opening;
  while ((opening = TAG_OPEN_SCAN.exec(payload)) !== null) {
    if (opening.index < consumed) continue;
    if (closing < TAG_OPEN_SCAN.lastIndex) {
      closing = payload.indexOf('>', TAG_OPEN_SCAN.lastIndex);
    }
    if (closing === -1) break;
    count++;
    consumed = closing + 1;
  }
  return count;
}

function htmlTagDensity(payload, tokenCount) {
  const tagCount = countOpenTags(payload);
  if (!tagCount) return 0;
  return round4(tagCount / Math.max(1, tokenCount));
}

function decodeFormValue(value) {
  // urllib.parse.parse_qsl uses unquote_plus: '+' becomes a space, then %XX is
  // decoded.  pythonUnquote matches Python's UTF-8 replacement behaviour.
  return pythonUnquote(value.replace(/\+/g, ' '));
}

function parameterValues(payload) {
  const spaceIndex = payload.indexOf(' ');
  const target = spaceIndex === -1 ? payload : payload.slice(0, spaceIndex);
  const body = spaceIndex === -1 ? '' : payload.slice(spaceIndex + 1);
  const queryIndex = target.indexOf('?');
  const query = queryIndex === -1 ? '' : target.slice(queryIndex + 1);
  const values = [];
  for (const text of [query, body]) {
    if (!text) continue;
    for (const pair of text.split('&')) {
      if (!pair) continue;
      const equals = pair.indexOf('=');
      values.push(decodeFormValue(equals === -1 ? '' : pair.slice(equals + 1)));
    }
  }
  return values;
}

function maxValueFeatures(values) {
  if (!values.length) return [0, 0];
  let maxSpecial = 0;
  let maxLength = 0;
  for (const value of values) {
    const length = codePointLength(value);
    if (length > maxLength) maxLength = length;
    if (!length) continue;
    // Python str.isalnum()/isspace(): Unicode letters/numbers and whitespace.
    const special = (value.match(/[^\p{L}\p{N}\s]/gu) || []).length;
    const ratio = special / length;
    if (ratio > maxSpecial) maxSpecial = ratio;
  }
  return [round4(maxSpecial), maxLength];
}

function countOccurrences(text, needle) {
  let count = 0;
  let index = 0;
  while ((index = text.indexOf(needle, index)) !== -1) {
    count++;
    index += needle.length;
  }
  return count;
}

function lexicalFeatures(payload) {
  const target = payload.split(' ', 1)[0];
  const path = target.split('?', 1)[0].toLowerCase();
  const raw = payload.toLowerCase();
  const [maxSpecial, maxLength] = maxValueFeatures(parameterValues(payload));
  return {
    suspicious_extension_flag: SUSPICIOUS_EXTENSIONS.some((extension) => path.endsWith(extension)) ? 1 : 0,
    quote_count: countOccurrences(raw, "'") + countOccurrences(raw, '"') + countOccurrences(raw, '%27') + countOccurrences(raw, '%22'),
    angle_count: countOccurrences(raw, '<') + countOccurrences(raw, '>') + countOccurrences(raw, '%3c') + countOccurrences(raw, '%3e'),
    double_escape_count: (raw.match(DOUBLE_ESCAPE_PATTERN) || []).length,
    max_value_special_ratio: maxSpecial,
    max_value_length: maxLength,
  };
}

/**
 * Extract the 22-D v3 vector, the 16-D v2 vector, or the 10-D v1 baseline.
 * @param {string} payload - normalized URL + body string
 * @param {string} userAgent
 * @param {string} method
 * @param {'v1'|'v2'|'v3'} version
 * @returns {Object<string, number>}
 */
function extractFeatures(payload, userAgent = '', method = 'GET', version = 'v3') {
  const payloadStr = sliceCodePoints(String(payload ?? ''), MAX_PAYLOAD_CHARS);
  const uaStr = String(userAgent ?? '').toLowerCase();
  const methodStr = String(method || 'GET').toUpperCase();
  const length = codePointLength(payloadStr);
  const lowerPayload = payloadStr.toLowerCase();
  const decodedPayload = pythonUnquote(payloadStr).toLowerCase();
  const combinedPayload = `${lowerPayload} ${decodedPayload}`;
  const trimmed = payloadStr.trim();
  const tokenCount = trimmed ? trimmed.split(/\s+/).length : 0;

  // Classify with code-point arithmetic instead of a regex call per character;
  // only non-ASCII code points pay for the Unicode whitespace test.
  let specialCharCount = 0;
  let digitCount = 0;
  let uppercaseCount = 0;
  for (const char of payloadStr) {
    const code = char.codePointAt(0);
    const isDigit = code >= 48 && code <= 57;
    const isUpper = code >= 65 && code <= 90;
    const isLower = code >= 97 && code <= 122;
    const isAsciiSpace = code === 32 || (code >= 9 && code <= 13);
    const isSpace = isAsciiSpace || (code > 127 && /\s/.test(char));
    if (!(isDigit || isUpper || isLower || isSpace)) specialCharCount++;
    if (isDigit) digitCount++;
    else if (isUpper) uppercaseCount++;
  }

  const features = {
    payload_length: length,
    shannon_entropy: calculateShannonEntropy(payloadStr),
    special_char_ratio: length ? round4(specialCharCount / length) : 0,
    digit_ratio: length ? round4(digitCount / length) : 0,
    uppercase_ratio: length ? round4(uppercaseCount / length) : 0,
    token_count: tokenCount,
    sql_keyword_score: countKeywordHits(combinedPayload, SQL_KEYWORDS),
    xss_keyword_score: countKeywordHits(combinedPayload, XSS_KEYWORDS),
    path_traversal_score: countKeywordHits(combinedPayload, TRAVERSAL_KEYWORDS),
    user_agent_anomaly: KNOWN_SCANNER_UAS.some((scanner) => uaStr.includes(scanner)) ? 1 : 0,
  };

  if (version === 'v1') return features;

  features.command_injection_score = commandInjectionScore(combinedPayload);
  features.hex_encoding_ratio = hexEncodingRatio(payloadStr, length);
  features.null_byte_score = NULL_BYTE_PATTERN.test(payloadStr) ? 1 : 0;
  features.param_pollution_count = paramPollutionCount(payloadStr);
  features.html_tag_density = htmlTagDensity(payloadStr, tokenCount);
  features.request_method_risk = METHOD_RISK_WEIGHTS[methodStr] ?? 0.5;

  if (version === 'v2') return features;

  Object.assign(features, lexicalFeatures(payloadStr));
  return features;
}

function namesForVersion(version) {
  if (version === 'v1') return V1_FEATURE_NAMES;
  if (version === 'v2') return V2_FEATURE_NAMES;
  return V3_FEATURE_NAMES;
}

function featureDictToVector(features, version = 'v3') {
  return namesForVersion(version).map((name) => features[name] ?? 0);
}

/**
 * Gateway mode prefixes every request with /p/<slug>.  Strip it before
 * feature extraction so the ratios and lexical scores match the origin path
 * the model was trained on (and the direct local test).
 */
function stripGatewayPrefix(url) {
  const match = /^\/p\/[^/?#]+/.exec(url || '');
  if (!match) return url;
  return url.slice(match[0].length) || '/';
}

/**
 * Build the same normalized payload string that the Python service sees.
 * Keeping one helper prevents the proxy's local extraction and the ML call
 * from drifting apart.
 */
function buildPayloadFromRequest(req) {
  const url = stripGatewayPrefix(req.originalUrl || req.url || '/');
  let bodyText = '';
  if (req.bodyParseFailed && req.rawBodyText) {
    bodyText = req.rawBodyText;
  } else if (typeof req.body === 'string') {
    bodyText = req.body;
  } else if (req.body !== undefined && req.body !== null) {
    try {
      bodyText = JSON.stringify(req.body);
    } catch {
      bodyText = req.rawBodyText || '';
    }
  } else if (req.rawBodyText) {
    bodyText = req.rawBodyText;
  }
  return sliceCodePoints(`${url} ${bodyText}`, MAX_PAYLOAD_CHARS);
}

function extractFeatureBundle(req, version = 'v3') {
  const start = process.hrtime.bigint();
  const payload = buildPayloadFromRequest(req);
  const features = extractFeatures(payload, req.headers?.['user-agent'] || '', req.method || 'GET', version);
  const vector = featureDictToVector(features, version);
  const extractionMs = Number(process.hrtime.bigint() - start) / 1e6;
  return {
    version,
    names: namesForVersion(version),
    payload,
    features,
    vector,
    extractionMs,
  };
}

/**
 * Conservative multi-signal risk score in [0, 1].
 * A single strong rule is left to the explicit regex detectors; this layer
 * exists to combine orthogonal feature evidence and to keep the vector useful
 * if the optional ML service is offline.
 */
function scoreFeatureRisk(features) {
  if (!features || typeof features !== 'object') return 0;
  let score = 0;

  if (features.user_agent_anomaly) score += 0.20;
  if (features.null_byte_score) score += 0.45;
  if (features.command_injection_score > 0) score += Math.min(0.40, 0.20 * features.command_injection_score);
  if (features.sql_keyword_score > 0) score += Math.min(0.35, 0.12 * features.sql_keyword_score);
  if (features.xss_keyword_score > 0) score += Math.min(0.35, 0.12 * features.xss_keyword_score);
  if (features.path_traversal_score > 0) score += Math.min(0.30, 0.12 * features.path_traversal_score);
  if (features.hex_encoding_ratio > 0.35) score += Math.min(0.15, features.hex_encoding_ratio * 0.15);
  if (features.param_pollution_count > 0) score += Math.min(0.10, features.param_pollution_count * 0.05);
  if (features.html_tag_density > 0.75) score += Math.min(0.15, features.html_tag_density * 0.05);
  if (features.request_method_risk >= 0.8) score += 0.20;
  if (features.shannon_entropy > 4.5 && features.payload_length >= 80) score += 0.08;
  if (features.payload_length >= 1000) score += 0.05;

  return Math.min(1, Math.round(score * 1000) / 1000);
}

module.exports = {
  FEATURE_NAMES,
  V1_FEATURE_NAMES,
  V2_FEATURE_NAMES,
  V3_FEATURE_NAMES,
  FEATURE_GROUPS,
  FEATURE_DESCRIPTIONS,
  FEATURE_RISK_THRESHOLD,
  METHOD_RISK_WEIGHTS,
  MAX_PAYLOAD_CHARS,
  calculateShannonEntropy,
  codePointLength,
  pythonUnquote,
  extractFeatures,
  featureDictToVector,
  buildPayloadFromRequest,
  stripGatewayPrefix,
  extractFeatureBundle,
  scoreFeatureRisk,
};
