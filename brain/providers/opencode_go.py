import hashlib
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from brain.providers.base import InferenceRequest, InferenceResponse, ProviderError

ENDPOINT = "https://opencode.ai/inference/go/openai/v1/chat/completions"


class OpenCodeGoAdapter:
    name = "opencode_go"

    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str):
        if not api_key.strip():
            raise ValueError("Missing OPENCODE_GO_API_KEY")
        if not model.strip():
            raise ValueError("Missing INFERENCE_MODEL")
        self.client, self.api_key, self.model = client, api_key, model

    @classmethod
    def from_env(cls, client: httpx.AsyncClient) -> "OpenCodeGoAdapter":
        if os.environ.get("INFERENCE_PROVIDER", "opencode_go") != "opencode_go":
            raise ValueError("Unsupported INFERENCE_PROVIDER")
        return cls(client, os.environ.get("OPENCODE_GO_API_KEY", ""),
                   os.environ.get("INFERENCE_MODEL", ""))

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "devhack-oncall-agent/0.1",
            "x-opencode-session": hashlib.sha256(request.incident_id.encode()).hexdigest(),
        }
        try:
            response = await self.client.post(
                ENDPOINT, headers=headers,
                json={"model": self.model, "messages": request.messages,
                      "max_tokens": request.max_tokens, "stream": False},
                timeout=30, follow_redirects=False,
            )
        except httpx.RequestError:
            raise ProviderError("transport_failure", retryable=True) from None
        if response.status_code >= 400:
            retry_after = 0.0
            raw = response.headers.get("retry-after", "0")
            try:
                retry_after = max(0.0, float(raw))
            except ValueError:
                try:
                    retry_after = max(0.0, (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError):
                    pass
            raise ProviderError(f"http_{response.status_code}",
                                response.status_code in (408, 429) or response.status_code >= 500,
                                retry_after)
        try:
            body = response.json()
            choice = body["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str) or choice.get("finish_reason") == "length":
                raise ValueError
            return InferenceResponse(content, self.name, self.model, body.get("usage", {}),
                                     response.headers.get("x-request-id"), choice.get("finish_reason"))
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("invalid_response", retryable=True) from None
