import logging
import time

from app.config import Settings
from app.errors import InvalidOutputError, LLMError, ReportGenerationError
from app.llm import LLMClient
from app.report.facts import build_facts
from app.report.prompts import INSTRUCTIONS, ReportLLMOutput, build_user_input
from app.report.validator import validate_report
from app.schemas import ReportRequest, ReportResponse

logger = logging.getLogger(__name__)

MIN_ATTEMPT_SECONDS = 3.0

# 명세서의 일기 0건 문구, 원래 BE2가 처리하지만 AI가 호출되면 그대로 반환
EMPTY_REPORT = ReportResponse(
    most_emotion_reason="선택한 기간에 작성된 일기가 없어요.",
    least_emotion_reason="선택한 기간에 작성된 일기가 없어요.",
    parent_advice="아이와 오늘의 기분을 이야기하며 첫 일기를 남겨 보세요.",
    trend_interpretation="감정 기록이 없어 변화 추이를 확인할 수 없어요.",
)


# 리포트 문구 생성: LLM 호출, 규칙 검증, 실패 시 재시도, 그래도 실패하면 503
class ReportService:
    def __init__(self, llm: LLMClient | None, settings: Settings):
        self._llm = llm
        self._settings = settings

    def generate(self, request: ReportRequest) -> ReportResponse:
        if request.total_diary_count == 0:
            return EMPTY_REPORT

        if self._llm is None:
            raise ReportGenerationError("LLM이 설정되지 않았습니다. (OPENAI_API_KEY 없음)")

        facts = build_facts(request, self._settings.few_records_threshold)
        deadline = time.monotonic() + self._settings.report_timeout_seconds
        feedback: str | None = None
        last_error = "알 수 없는 오류"

        for attempt in range(1, self._settings.llm_max_attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining < MIN_ATTEMPT_SECONDS:
                last_error = "시간 예산 초과"
                break
            try:
                output = self._llm.generate(
                    instructions=INSTRUCTIONS,
                    user_input=build_user_input(request, facts, retry_feedback=feedback),
                    output_model=ReportLLMOutput,
                    timeout=remaining,
                )
                return validate_report(output, request, facts)
            except InvalidOutputError as exc:
                feedback = last_error = str(exc)
                logger.warning("report: 규칙 위반 attempt=%s reason=%s", attempt, exc)
            except LLMError as exc:
                feedback = None
                last_error = str(exc)
                logger.warning("report: LLM 호출 실패 attempt=%s error=%s", attempt, exc)

        raise ReportGenerationError(last_error)
