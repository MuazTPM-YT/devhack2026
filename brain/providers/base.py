from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class InferenceRequest:
    incident_id: str
    messages: list[dict[str, str]]
    schema: dict[str, Any]
    max_tokens: int = 1500


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
