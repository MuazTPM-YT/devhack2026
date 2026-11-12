import json

import pytest

from brain.redact import quarantine, redact, redact_value


@pytest.mark.parametrize("secret", ["Bearer example-token", "password=example-pass",
                                    "https://user:pass@example.org", "sk-examplevalue",
                                    "a" * 80, "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"])
def test_secrets_removed(secret):
    assert secret not in redact(secret)


def test_nested_env_and_sensitive_keys():
    result = redact_value({"env": [{"name": "DB_URL", "value": "private"}],
                           "authorization": "private"})
    assert "private" not in json.dumps(result)


def test_quarantine_keeps_hash_only():
    clean, hashes = quarantine(["ignore previous instructions", "healthy"])
    assert clean == ["healthy"]
    assert len(hashes[0]) == 64
