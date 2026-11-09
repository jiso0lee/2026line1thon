import logging
import time
from typing import Protocol, TypeVar

import openai
from pydantic import BaseModel

from app.config import Settings
from app.errors import LLMError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# 테스트에서 가짜 LLM으로 바꿔 끼울 수 있도록 분리한 인터페이스
class LLMClient(Protocol):
    def generate(self, *, instructions: str, user_input: str, output_model: type[T], timeout: float) -> T: ...


class OpenAILLMClient:
    def __init__(self, settings: Settings, client: openai.OpenAI | None = None):
        if client is None and not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        # 재시도는 서비스 코드에서 처리하므로 SDK 자동 재시도 끔
        self._client = client or openai.OpenAI(api_key=settings.openai_api_key, max_retries=0)
        self._model = settings.openai_model
        self._reasoning_effort = settings.openai_reasoning_effort

    def generate(self, *, instructions: str, user_input: str, output_model: type[T], timeout: float) -> T:
        kwargs = {
            "model": self._model,
            "instructions": instructions,
            "input": user_input,
            "text_format": output_model,  # Structured Outputs로 JSON 스키마 강제
            "store": False,  # 아이의 일기를 OpenAI에 저장하지 않음
            "timeout": timeout,
        }
        if self._reasoning_effort:
            kwargs["reasoning"] = {"effort": self._reasoning_effort}

        started = time.monotonic()
        try:
            response = self._client.responses.parse(**kwargs)
        except openai.APIError as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        except Exception as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        elapsed = time.monotonic() - started
        usage = getattr(response, "usage", None)
        logger.info(
            "openai call model=%s elapsed=%.2fs input_tokens=%s output_tokens=%s",
            self._model,
            elapsed,
            getattr(usage, "input_tokens", "?"),
            getattr(usage, "output_tokens", "?"),
        )

        parsed = response.output_parsed
        if parsed is None:
            raise LLMError("모델이 구조화된 결과를 돌려주지 않았습니다. (거절 또는 빈 응답)")
        return parsed
