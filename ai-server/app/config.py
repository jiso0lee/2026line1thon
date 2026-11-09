import os
from dataclasses import dataclass


def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_float(name: str, default: float) -> float:
    value = _env_str(name)
    return float(value) if value is not None else default


def _env_int(name: str, default: int) -> int:
    value = _env_str(name)
    return int(value) if value is not None else default


@dataclass(frozen=True)
class Settings:
    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    # 추론 모델의 reasoning effort, 빈 값이면 파라미터 미전송
    openai_reasoning_effort: str | None = "low"

    # 요청 1건의 전체 시간 예산(초), 재시도 포함
    question_timeout_seconds: float = 12.0
    report_timeout_seconds: float = 25.0

    llm_max_attempts: int = 2

    ai_api_key: str | None = None

    few_records_threshold: int = 7

    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            openai_api_key=_env_str("OPENAI_API_KEY"),
            openai_model=_env_str("OPENAI_MODEL", cls.openai_model),
            openai_reasoning_effort=_env_str("OPENAI_REASONING_EFFORT", cls.openai_reasoning_effort),
            question_timeout_seconds=_env_float("QUESTION_TIMEOUT_SECONDS", cls.question_timeout_seconds),
            report_timeout_seconds=_env_float("REPORT_TIMEOUT_SECONDS", cls.report_timeout_seconds),
            llm_max_attempts=max(1, _env_int("LLM_MAX_ATTEMPTS", cls.llm_max_attempts)),
            ai_api_key=_env_str("AI_API_KEY"),
            few_records_threshold=_env_int("FEW_RECORDS_THRESHOLD", cls.few_records_threshold),
            log_level=_env_str("LOG_LEVEL", cls.log_level),
        )
