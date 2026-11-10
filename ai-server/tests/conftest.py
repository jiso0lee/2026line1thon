import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import LLMError
from app.main import create_app


# 미리 넣어 둔 결과를 차례로 돌려주는 가짜 LLM, 예외 객체면 그 예외 발생
class FakeLLM:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def generate(self, *, instructions, user_input, output_model, timeout):
        self.calls.append({"instructions": instructions, "user_input": user_input, "timeout": timeout})
        if not self.outputs:
            raise LLMError("no more fake outputs")
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        if "risk" in output_model.model_fields and "risk" not in item:
            item = {"risk": False, **item}
        return output_model(**item)


@pytest.fixture
def settings():
    return Settings(openai_api_key=None, llm_max_attempts=2)


@pytest.fixture
def make_client(settings):
    def _make(llm=None, **overrides):
        s = Settings(**{**settings.__dict__, **overrides})
        return TestClient(create_app(s, llm=llm))

    return _make


@pytest.fixture
def question_body():
    return {
        "emotion": "JOY",
        "content": "오늘 친구와 운동장에서 공놀이를 했다. 친구가 나에게 공을 넘겨줘서 골을 넣었다.",
        "order": 2,
        "type": "REASON",
        "previousAnswers": [
            {
                "order": 1,
                "type": "EMOTION",
                "question": "골을 넣었을 때 어떤 기분이 들었니?",
                "answer": "정말 신나고 친구한테 고마웠어요.",
            }
        ],
    }


@pytest.fixture
def report_body():
    return {
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


GOOD_REPORT = {
    "most_emotion_reason": "선택한 기간에는 기쁨을 2회로 가장 자주 기록했어요.",
    "least_emotion_reason": "화남, 무서움, 놀람, 부끄러움은 선택한 기간에 기록되지 않았어요.",
    "parent_advice": "아이와 즐거웠던 순간을 이야기하고, 슬펐던 날의 마음도 편안하게 들어 주세요.",
    "trend_interpretation": "기쁨, 슬픔, 기쁨 순으로 기록했어요. 이 기록만으로 장기적인 변화를 판단하기는 어려워요.",
}
