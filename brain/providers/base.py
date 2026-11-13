from dataclasses import dataclass
from typing import Any, Protocol

# live bundles: calls took 16-20 s, then hit 30 s and 45 s; rules still act if this runs out
DEADLINE_S = 90


@dataclass(frozen=True)
class InferenceRequest:
    incident_id: str
    messages: list[dict[str, str]]
    schema: dict[str, Any]
    max_tokens: int = 4000  # reasoning counts here; live answers used ~900-1100


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
