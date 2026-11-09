import pytest

from app.errors import InvalidOutputError, LLMError
from app.report.facts import build_facts
from app.report.prompts import ReportLLMOutput, build_user_input
from app.report.validator import validate_report
from app.schemas import ReportRequest
from tests.conftest import GOOD_REPORT, FakeLLM

URL = "/api/emotion-reports/generate"


def test_generates_report(make_client, report_body):
    llm = FakeLLM(GOOD_REPORT)
    res = make_client(llm).post(URL, json=report_body)
    assert res.status_code == 200
    assert res.json() == GOOD_REPORT
    prompt = llm.calls[0]["user_input"]
    assert "가장 많이 기록한 감정: 기쁨 (2건)" in prompt
    assert "가장 적게 기록한 감정: 화남, 무서움, 놀람, 부끄러움 (0건)" in prompt
    assert "11월 1일 기쁨 → 11월 2일 슬픔 → 11월 3일 기쁨" in prompt
    assert "기록 양: 적음" in prompt


def test_zero_diaries_returns_spec_text_without_llm(make_client, report_body):
    body = {
        **report_body,
        "totalDiaryCount": 0,
        "distribution": [{**d, "count": 0, "ratio": 0} for d in report_body["distribution"]],
        "days": [{**d, "emotions": []} for d in report_body["days"]],
    }
    llm = FakeLLM()
    res = make_client(llm).post(URL, json=body)
    assert res.status_code == 200
    assert res.json()["most_emotion_reason"] == "선택한 기간에 작성된 일기가 없어요."
    assert llm.calls == []


def test_retry_then_success(make_client, report_body):
    bad = {**GOOD_REPORT, "most_emotion_reason": "기쁨을 약 67%로 가장 자주 기록했어요."}  # 반올림한 숫자
    llm = FakeLLM(bad, GOOD_REPORT)
    res = make_client(llm).post(URL, json=report_body)
    assert res.status_code == 200
    assert "67" in llm.calls[1]["user_input"]  # 재시도 피드백 확인


def test_returns_503_when_generation_fails(make_client, report_body):
    res = make_client(FakeLLM(LLMError("down"), LLMError("down"))).post(URL, json=report_body)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "AI_GENERATION_FAILED"


def test_returns_503_without_openai_key(make_client, report_body):
    assert make_client(llm=None).post(URL, json=report_body).status_code == 503


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda b: b["distribution"].pop(), "감정 6종"),
        (lambda b: b.update(totalDiaryCount=5), "합계"),
        (lambda b: b.update(endDate="2026-10-01"), "endDate"),
        (lambda b: b["days"].append({"date": "2026-12-01", "emotions": []}), "기간 밖"),
        (lambda b: b["days"].reverse(), "날짜순"),
    ],
)
def test_rejects_inconsistent_requests(make_client, report_body, mutate, expected):
    mutate(report_body)
    res = make_client(FakeLLM()).post(URL, json=report_body)
    assert res.status_code == 422
    assert any(expected in d for d in res.json()["error"]["details"])

# 최다·최소 감정 정리
def _request(counts: dict[str, int], days=None) -> ReportRequest:
    total = sum(counts.values())
    distribution = [
        {"emotion": e, "count": counts.get(e, 0), "ratio": round(counts.get(e, 0) / total * 100, 2) if total else 0}
        for e in ["JOY", "SADNESS", "ANGER", "FEAR", "SURPRISE", "SHAME"]
    ]
    return ReportRequest.model_validate(
        {"startDate": "2026-11-01", "endDate": "2026-11-10", "totalDiaryCount": total,
         "distribution": distribution, "days": days or []}
    )


def test_facts_ties():
    facts = build_facts(_request({"JOY": 2, "ANGER": 2, "FEAR": 1}), few_records_threshold=7)
    assert [i.emotion.value for i in facts.most] == ["JOY", "ANGER"]
    assert [i.emotion.value for i in facts.least] == ["SADNESS", "SURPRISE", "SHAME"]
    assert facts.few_records is True


def test_facts_all_equal():
    req = _request({e: 1 for e in ["JOY", "SADNESS", "ANGER", "FEAR", "SURPRISE", "SHAME"]})
    facts = build_facts(req, few_records_threshold=7)
    assert facts.all_equal is True
    assert "모든 감정을 같은 횟수" in build_user_input(req, facts)

# 출력 검증
def _validate(report_body, **override):
    req = ReportRequest.model_validate(report_body)
    facts = build_facts(req, few_records_threshold=7)
    return validate_report(ReportLLMOutput(**{**GOOD_REPORT, **override}), req, facts)


def test_validator_accepts_spec_example(report_body):
    assert _validate(report_body).model_dump() == GOOD_REPORT


@pytest.mark.parametrize(
    "field, text",
    [
        ("most_emotion_reason", "기쁨을 5회로 가장 자주 기록했어요."),  # 기록에 없는 숫자
        ("least_emotion_reason", "화남은 전혀 느끼지 않았어요."),  # 단정
        ("trend_interpretation", "기쁨이 늘면서 감정이 좋아졌어요."),  # 좋아졌다 단정
        ("parent_advice", "우울한 마음이 있는지 살펴보세요."),  # 진단성 표현
        ("parent_advice", "이야기를 들어 주세요. 함께 산책도 해 보세요."),  # 2문장
        ("most_emotion_reason", "JOY를 가장 많이 기록했어요."),  # 감정 코드
        ("trend_interpretation", ""),  # 빈 값
    ],
)
def test_validator_rejects(report_body, field, text):
    with pytest.raises(InvalidOutputError):
        _validate(report_body, **{field: text})


def test_validator_allows_given_ratio_and_dates(report_body):
    out = _validate(
        report_body,
        most_emotion_reason="기쁨이 66.67%로 가장 많았어요.",
        trend_interpretation="11월 1일 기쁨, 11월 2일 슬픔, 11월 3일 기쁨 순으로 기록했어요.",
    )
    assert "66.67%" in out.most_emotion_reason
