# 실제 OpenAI로 질문·리포트 확인 (크레딧 사용, ai-server 폴더에서 실행)
# python -m scripts.try_live: 질문 3개를 받고 터미널에 답변 직접 입력
# python -m scripts.try_live --report: 예시 데이터로 리포트 문구 생성

import argparse
import json
import logging

from dotenv import load_dotenv

load_dotenv()

from app.config import Settings  # noqa: E402
from app.domain import ORDER_TO_TYPE  # noqa: E402
from app.llm import OpenAILLMClient  # noqa: E402
from app.question.answers import is_uninformative  # noqa: E402
from app.question.service import QuestionService  # noqa: E402
from app.report.service import ReportService  # noqa: E402
from app.schemas import QuestionRequest, ReportRequest  # noqa: E402

SAMPLE_DIARY = "오늘 친구와 운동장에서 공놀이를 했다. 친구가 나에게 공을 넘겨줘서 골을 넣었다."

SAMPLE_REPORT = {
    "startDate": "2026-11-01",
    "endDate": "2026-11-03",
    "totalDiaryCount": 3,
    "distribution": [
        {"emotion": "JOY", "count": 2, "ratio": 66.67},
        {"emotion": "SADNESS", "count": 1, "ratio": 33.33},
        {"emotion": "ANGER", "count": 0, "ratio": 0},
        {"emotion": "FEAR", "count": 0, "ratio": 0},
        {"emotion": "SURPRISE", "count": 0, "ratio": 0},
        {"emotion": "SHAME", "count": 0, "ratio": 0},
    ],
    "days": [
        {"date": "2026-11-01", "emotions": ["JOY"]},
        {"date": "2026-11-02", "emotions": ["SADNESS"]},
        {"date": "2026-11-03", "emotions": ["JOY"]},
    ],
}


def run_questions(settings: Settings) -> None:
    service = QuestionService(OpenAILLMClient(settings), settings)
    emotion = input("감정 코드 (JOY/SADNESS/ANGER/FEAR/SURPRISE/SHAME) [JOY]: ").strip() or "JOY"
    content = input("일기 (엔터 = 예시 사용)\n> ").strip() or SAMPLE_DIARY

    previous: list[dict] = []
    for order in (1, 2, 3):
        body = {"emotion": emotion, "content": content, "order": order,
                "type": ORDER_TO_TYPE[order].value, "previousAnswers": previous}
        result = service.generate(QuestionRequest.model_validate(body))
        tag = " (기본 질문)" if result.is_fallback else ""
        print(f"\n[질문 {order}, {result.type.value}]{tag} {result.content}")
        question, answer = result.content, input("답변> ")

        # 빈 답변이나 몰라요면 같은 질문을 쉬운 말로 한 번만 다시 묻기
        if is_uninformative(answer):
            body["retry"] = {"question": question, "answer": answer}
            result = service.generate(QuestionRequest.model_validate(body))
            tag = " (기본 질문)" if result.is_fallback else ""
            print(f"[다시 묻기]{tag} {result.content}")
            question, answer = result.content, input("답변> ")

        previous.append({"order": order, "type": result.type.value, "question": question, "answer": answer})


def run_report(settings: Settings) -> None:
    service = ReportService(OpenAILLMClient(settings), settings)
    result = service.generate(ReportRequest.model_validate(SAMPLE_REPORT))
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    run_report(settings) if args.report else run_questions(settings)
