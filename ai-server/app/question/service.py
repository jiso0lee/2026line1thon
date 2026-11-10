import logging
import time

from app.config import Settings
from app.errors import InvalidOutputError, LLMError
from app.llm import LLMClient
from app.question.fallback import fallback_question
from app.question.prompts import INSTRUCTIONS, QuestionLLMOutput, build_user_input
from app.question.risk import detect_risk
from app.question.validator import validate_question
from app.schemas import QuestionRequest, QuestionResponse

logger = logging.getLogger(__name__)

# 남은 시간이 이보다 적으면 재시도 없이 기본 질문 사용
MIN_ATTEMPT_SECONDS = 2.0


# 질문 1개 생성: 위험 감지, LLM 호출, 규칙 검증, 실패 시 재시도, 그래도 실패하면 기본 질문
class QuestionService:
    def __init__(self, llm: LLMClient | None, settings: Settings):
        self._llm = llm
        self._settings = settings

    def generate(self, request: QuestionRequest) -> QuestionResponse:
        risk = detect_risk(*_texts(request))
        content, risk = self._try_llm(request, risk)
        if content is not None:
            return QuestionResponse(order=request.order, type=request.type, content=content, is_fallback=False)

        return QuestionResponse(
            order=request.order,
            type=request.type,
            content=fallback_question(request.type, request.emotion, risk=risk, retry=request.retry is not None),
            is_fallback=True,
        )

    # 반환값: (검증된 질문 또는 None, 최종 위험 여부)
    def _try_llm(self, request: QuestionRequest, risk: bool) -> tuple[str | None, bool]:
        if risk:
            logger.warning("question: 위험 내용 감지, 안전 모드 order=%s", request.order)
        if self._llm is None:
            logger.warning("question fallback: LLM 미설정(OPENAI_API_KEY 없음) order=%s", request.order)
            return None, risk

        deadline = time.monotonic() + self._settings.question_timeout_seconds
        feedback: str | None = None
        previous_question = request.retry.question if request.retry is not None else None

        for attempt in range(1, self._settings.llm_max_attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining < MIN_ATTEMPT_SECONDS:
                logger.warning("question: 시간 예산 부족으로 재시도 중단 attempt=%s", attempt)
                break
            try:
                output = self._llm.generate(
                    instructions=INSTRUCTIONS,
                    user_input=build_user_input(request, risk_detected=risk, retry_feedback=feedback),
                    output_model=QuestionLLMOutput,
                    timeout=remaining,
                )
                if output.risk and not risk:
                    # 코드가 놓친 위험 내용을 LLM이 찾으면 이후 시도와 기본 질문도 안전 모드
                    risk = True
                    logger.warning("question: LLM이 위험 내용 판단, 안전 모드 order=%s", request.order)
                question = validate_question(
                    output.question,
                    source_text=_source_text(request),
                    diary=request.content,
                    risk=risk,
                    previous_question=previous_question,
                )
                return question, risk
            except InvalidOutputError as exc:
                feedback = str(exc)
                logger.warning("question: 규칙 위반 attempt=%s order=%s reason=%s", attempt, request.order, exc)
            except LLMError as exc:
                feedback = None
                logger.warning("question: LLM 호출 실패 attempt=%s order=%s error=%s", attempt, request.order, exc)

        logger.warning("question fallback 사용 order=%s type=%s", request.order, request.type.value)
        return None, risk


def _texts(request: QuestionRequest) -> list[str]:
    texts = [request.content, *(item.answer or "" for item in request.previous_answers)]
    if request.retry is not None:
        texts.append(request.retry.answer or "")
    return texts


def _source_text(request: QuestionRequest) -> str:
    return "\n".join(_texts(request))
