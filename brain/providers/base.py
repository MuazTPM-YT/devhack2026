from dataclasses import dataclass
from typing import Any, Protocol

# live bundles: calls took 16-20 s, then hit 30 s and 45 s; rules still act if this runs out
DEADLINE_S = 90
# agent mode: whole tool loop (up to 6 rounds); each HTTP call still has DEADLINE_S
AGENT_DEADLINE_S = 150


@dataclass(frozen=True)
class InferenceRequest:
    incident_id: str
    messages: list[dict[str, str]]
    schema: dict[str, Any]
    # reasoning models (deepseek-v4.1-flash) spend hidden reasoning tokens from this budget: live answers
    # used 1444-1739 tokens, so 1500 (the plan's figure for a non-reasoning model) cut most of them off;
    # a datastore-down bundle still ran past 4096
    max_tokens: int = 8192


@dataclass(frozen=True)
class InferenceResponse:
    content: str
    provider: str
    model: str
    usage: dict[str, Any]
    request_id: str | None = None
    finish_reason: str | None = None


class ProviderError(Exception):
    def __init__(self, code: str, retryable: bool = False, retry_after: float = 0):
        super().__init__(code)
        self.retryable = retryable
        self.retry_after = retry_after


class InferenceProvider(Protocol):
    model: str
    name: str

    async def generate(self, request: InferenceRequest) -> InferenceResponse: ...
