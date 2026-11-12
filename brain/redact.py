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
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name in {"line_hash", "hash_before", "hash_after"} and isinstance(item, str) and re.fullmatch(r"[a-f0-9]{64}", item):
                result[name] = item
            elif isinstance(item, (int, float)) and name.endswith("tokens"):
                result[name] = item
            else:
                result[redact(name)] = "[REDACTED]" if SECRET_KEYS.search(name) else redact_value(item)
        if "name" in value and "value" in value:
            result["value"] = f"[REDACTED:env:{redact(str(value['name']))}]"
        return result
    return value


def quarantine(lines: list[str]) -> tuple[list[str], list[str]]:
    clean, hashes = [], []
    for line in lines:
        if INJECTION.search(line):
            hashes.append(hashlib.sha256(line.encode()).hexdigest())
        else:
            clean.append(redact(line))
    return clean, hashes
