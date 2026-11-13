# one durable reservation per provider call (handoff §7.4): commander, specialists, retries and resumes
# all draw on the incident's single budget in SQLite, so a restart or a new child never refills it.
import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

from schemas.workspace import Workspace

CHARS_PER_TOKEN = 4  # rough on purpose: a conservative over-estimate is the safe side
DEFAULT_OUTPUT = 8192


def estimate_input_tokens(messages: list[ModelMessage]) -> int:
    text = json.dumps([m.parts for m in messages], default=str)
    return len(text) // CHARS_PER_TOKEN + 1


class BudgetedModel(WrapperModel):
    def __init__(self, wrapped: Model, workspace: Workspace, incident_id: str, run_id: str,
                 role: Literal["commander", "specialist"], task_id: str | None = None, task_limit: int | None = None,
                 publish: Callable[[str, str | None, dict], Awaitable[None]] | None = None,
                 clock: Callable[[], float] = time.time):
        super().__init__(wrapped)
        self.ws, self.incident_id, self.run_id, self.role = workspace, incident_id, run_id, role
        self.task_id, self.task_limit, self.publish, self.clock = task_id, task_limit, publish, clock

    async def request(self, messages: list[ModelMessage], model_settings: ModelSettings | None,
                      model_request_parameters: ModelRequestParameters) -> ModelResponse:
        estimate = estimate_input_tokens(messages)
        per_request = self.ws.policy.max_input_tokens_per_request
        if per_request is not None and estimate > per_request:
            raise UsageLimitExceeded(f"token_budget: request of ~{estimate} tokens exceeds {per_request}")
        output = int((model_settings or {}).get("max_tokens") or DEFAULT_OUTPUT)
        call_id = f"call-{uuid.uuid4().hex[:16]}"
        denied = self.ws.reserve_call(call_id, self.incident_id, self.run_id, self.role, self.task_id,
                                      reserved_tokens=estimate + output, task_limit=self.task_limit)
        if denied:
            raise UsageLimitExceeded(f"{denied}: incident model budget used up")
        started = self.clock()
        try:
            response = await self.wrapped.request(messages, model_settings, model_request_parameters)
        except asyncio.CancelledError:  # the provider may still bill a request we stopped waiting for
            self.ws.settle_call(call_id, "unknown", error="cancelled")
            raise
        except Exception as e:
            self.ws.settle_call(call_id, "error", error=type(e).__name__)
            raise
        usage = response.usage
        self.ws.settle_call(call_id, "ok", usage.input_tokens, usage.output_tokens)
        if self.publish is not None:
            await self.publish("llm_called", self.incident_id, {
                "provider": "opencode_go", "model": self.model_name, "kind": "call", "call_id": call_id,
                "task_id": self.task_id, "role": self.role, "ms": round((self.clock() - started) * 1000),
                "usage": {"prompt_tokens": usage.input_tokens, "completion_tokens": usage.output_tokens,
                          "requests": 1}})
        return response

    # streaming is not reserved per call yet: refuse rather than spend outside the budget
    @asynccontextmanager
    async def request_stream(self, messages: list[ModelMessage], model_settings: ModelSettings | None,
                             model_request_parameters: ModelRequestParameters,
                             run_context: Any = None) -> AsyncIterator[StreamedResponse]:
        raise NotImplementedError("streamed requests are not budgeted")
        yield  # type: ignore[unreachable]
