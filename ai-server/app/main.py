import logging
import secrets

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings
from app.errors import ReportGenerationError
from app.llm import LLMClient, OpenAILLMClient
from app.question.service import QuestionService
from app.report.service import ReportService
from app.schemas import (
    ErrorResponse,
    QuestionRequest,
    QuestionResponse,
    ReportRequest,
    ReportResponse,
)

logger = logging.getLogger("app")


class _Unauthorized(Exception):
    pass


def _error(status: int, code: str, message: str, details: list[str] | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if llm is None and settings.openai_api_key:
        llm = OpenAILLMClient(settings)
    if llm is None:
        logger.warning("OPENAI_API_KEY가 없습니다. 질문은 기본 질문, 리포트는 항상 503으로 응답합니다.")

    question_service = QuestionService(llm, settings)
    report_service = ReportService(llm, settings)

    app = FastAPI(
        title="생각의힘 AI 서버",
        version="0.1.0",
        description="AI 질문 생성 / 감정 리포트 문구 생성 API",
    )

    def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
        if settings.ai_api_key is None:
            return
        if x_api_key is None or not secrets.compare_digest(x_api_key, settings.ai_api_key):
            raise _Unauthorized()

    # 오류 처리
    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(_: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            location = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
            message = err.get("msg", "").removeprefix("Value error, ")
            details.append(f"{location}: {message}" if location else message)
        return _error(422, "INVALID_REQUEST", "요청 형식 오류", details)

    @app.exception_handler(ReportGenerationError)
    async def _on_report_error(_: Request, exc: ReportGenerationError):
        logger.error("report 생성 실패: %s", exc)
        return _error(503, "AI_GENERATION_FAILED", "리포트 문구를 생성하지 못했습니다. 기본 문구를 사용해 주세요.")

    @app.exception_handler(_Unauthorized)
    async def _on_unauthorized(_: Request, __: Exception):
        return _error(401, "UNAUTHORIZED", "X-API-Key 헤더가 없거나 올바르지 않습니다.")

    # 라우트
    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "llm": "configured" if llm is not None else "missing"}

    @app.post(
        "/api/diary-questions/generate",
        response_model=QuestionResponse,
        response_model_by_alias=True,
        tags=["question"],
        summary="일기 질문 생성",
        responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
        dependencies=[Depends(verify_api_key)],
    )
    def generate_question(request: QuestionRequest) -> QuestionResponse:
        return question_service.generate(request)

    @app.post(
        "/api/emotion-reports/generate",
        response_model=ReportResponse,
        tags=["report"],
        summary="감정 리포트 설명 문구 생성",
        responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
        dependencies=[Depends(verify_api_key)],
    )
    def generate_report(request: ReportRequest) -> ReportResponse:
        return report_service.generate(request)

    return app


app = create_app()
