import hashlib
import re
from typing import Any

INJECTION = re.compile(r"ignore\s+(?:all|previous)\s+instructions|you must\s+(?:run|execute|delete)|as an ai|system prompt", re.I)
PATTERNS = [
    r"-----BEGIN [^-]*KEY-----[\s\S]*?-----END [^-]*KEY-----",
    r"(?i)bearer\s+[^\s\"']+",
    r"(?i)(?:api[_-]?key|password|token|secret)\s*[=:]\s*[^\s,;\"']+",
    r"(?<=://)[^/@\s]+:[^/@\s]+@",
    r"\b(?:sk-|ghp_|xox[baprs]-)[A-Za-z0-9_-]+",
    r"\b[A-Fa-f0-9]{40,}\b",
    r"\b[A-Za-z0-9+/]{64,}={0,2}\b",
]
SECRET_KEYS = re.compile(r"password|secret|token|api[_-]?key|authorization", re.I)


def redact(text: str) -> str:
    for pattern in PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        if "name" in value and "value" in value:
            return {**value, "value": f"[REDACTED:env:{value['name']}]"}
        return {
            redact(str(key)): "[REDACTED]" if SECRET_KEYS.search(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    return value


def quarantine(lines: list[str]) -> tuple[list[str], list[str]]:
    clean, hashes = [], []
    for line in lines:
        if INJECTION.search(line):
            hashes.append(hashlib.sha256(line.encode()).hexdigest())
        else:
            clean.append(redact(line))
    return clean, hashes
