import pytest

from app.domain import Emotion, QuestionType
from app.errors import InvalidOutputError
from app.question.fallback import RISK_RETRY_FALLBACK, fallback_question, risk_fallback
from app.question.risk import detect_risk
from app.question.validator import validate_question
from tests.conftest import FakeLLM

URL = "/api/diary-questions/generate"
CHECK_URL = "/api/diary-answers/check"
RISK_DIARY = "아빠가 때려서 무서웠다. 방에서 혼자 울었다."


def _risk_body(order=3, qtype="PERSPECTIVE"):
    previous = [
        {"order": 1, "type": "EMOTION", "question": "지금은 마음이 어떠니?", "answer": "아직 무서워요"},
        {"order": 2, "type": "REASON", "question": "지금 가장 필요한 도움은 무엇이니?", "answer": "몰라요"},
    ][: order - 1]
    return {"emotion": "FEAR", "content": RISK_DIARY, "order": order, "type": qtype, "previousAnswers": previous}


# 위험 내용 감지
@pytest.mark.parametrize(
    "text",
    [
        "아빠가 때려서 무서웠다",
        "형한테 맞았다",
        "반 친구들이 나를 따돌린다",
        "죽고 싶다는 생각이 들었다",
        "삼촌이 아무한테도 말하지 말라고 했다",
        "엄마가 밥을 안 줘서 배고팠다",
    ],
)
def test_detect_risk(text):
    assert detect_risk(text) is True


@pytest.mark.parametrize(
    "text",
    ["시험 문제를 다 맞았다", "병원에서 주사를 맞았다", "공에 맞아서 아팠다", "모기를 죽였다", "친구랑 싸워서 속상했다"],
)
def test_no_risk_in_everyday_text(text):
    assert detect_risk(text) is False


def test_risk_detected_in_answer_too():
    assert detect_risk("오늘 학교에 갔다", "사실 형이 자꾸 때려요") is True


# 안전 모드 질문
def test_risk_prompt_uses_safety_goal(make_client):
    llm = FakeLLM({"risk": True, "question": "지금도 위험하다고 느껴지면, 선생님이나 믿을 수 있는 어른에게 말할 수 있을까?"})
    res = make_client(llm).post(URL, json=_risk_body())
    assert res.status_code == 200
    assert res.json()["isFallback"] is False
    prompt = llm.calls[0]["user_input"]
    assert "[안전 모드]" in prompt
    assert "안전 모드 도움 요청" in prompt  # 3번 질문 목적이 관점 확장 대신 도움 요청


def test_aggressor_perspective_question_is_replaced(make_client):
    llm = FakeLLM({"risk": True, "question": "아빠는 그때 왜 그랬을까?"}, {"risk": True, "question": "아빠는 어떤 마음이었을까?"})
    res = make_client(llm).post(URL, json=_risk_body())
    assert res.json() == {
        "order": 3,
        "type": "PERSPECTIVE",
        "content": risk_fallback(QuestionType.PERSPECTIVE, Emotion.FEAR),
        "isFallback": True,
    }
    assert "상대의 마음이나 이유" in llm.calls[1]["user_input"]


def test_risk_fallback_without_llm(make_client):
    res = make_client(llm=None).post(URL, json=_risk_body(order=2, qtype="REASON"))
    assert res.json()["content"] == "무서운 마음이 들 수 있어, 지금 무엇이 있으면 마음이 조금 편해질까?"


def test_llm_detected_risk_switches_to_safe_fallback(make_client):
    # 코드가 못 찾은 위험 내용을 LLM이 찾으면 기본 질문도 안전 모드
    body = {"emotion": "SADNESS", "content": "집에 가기 싫다. 오늘도 혼날까 봐 숨어 있었다.", "order": 3,
            "type": "PERSPECTIVE", "previousAnswers": _risk_body()["previousAnswers"]}
    llm = FakeLLM({"risk": True, "question": "그 사람은 왜 그랬을까?"}, {"risk": True, "question": "그 사람은 왜 그랬을까?"})
    res = make_client(llm).post(URL, json=body)
    assert res.json()["content"] == risk_fallback(QuestionType.PERSPECTIVE, Emotion.SADNESS)
    assert "[안전 모드]" in llm.calls[1]["user_input"]


@pytest.mark.parametrize(
    "question, reason",
    [
        ("아빠는 왜 그랬을까?", "상대의 마음"),
        ("엄마는 그때 어떤 마음이었을까?", "상대의 마음"),
        ("네가 뭘 했길래 그랬을까?", "아이 탓"),
        ("그때 있었던 일을 자세히 말해 줄래?", "세부 내용"),
        ("다음에는 참을 수 있을까?", "참거나"),
        ("엄마한테 도와 달라고 말할 수 있니?", "부모로만"),
        ("그 일은 네 잘못이 아니야, 지금 마음은 어떠니?", "잘잘못"),
        ("아빠가 잘못한 거야, 지금 마음은 어떠니?", "잘잘못"),
        ("아빠가 때려서 무서웠구나, 지금 마음은 어때?", "사실처럼"),
        ("그 일이 정말이야?", "의심"),
    ],
)
def test_risk_validator_rejects(question, reason):
    with pytest.raises(InvalidOutputError, match=reason):
        validate_question(question, diary=RISK_DIARY, risk=True)


def test_risk_mode_skips_scene_check():
    q = "솔직하게 이야기해 줘서 고마워, 지금은 마음이 어떠니?"
    assert validate_question(q, diary=RISK_DIARY, risk=True) == q
    with pytest.raises(InvalidOutputError):
        validate_question(q, diary=RISK_DIARY, risk=False)


def test_parent_with_other_adult_is_allowed():
    q = "엄마나 선생님처럼 믿을 수 있는 어른에게 도와 달라고 말할 수 있을까?"
    assert validate_question(q, risk=True) == q


@pytest.mark.parametrize("qtype", list(QuestionType))
@pytest.mark.parametrize("retry", [False, True])
def test_every_risk_fallback_passes_safety_rules(qtype, retry):
    q = fallback_question(qtype, Emotion.FEAR, risk=True, retry=retry)
    assert validate_question(q, diary=RISK_DIARY, risk=True) == q


# 몰라요 답변 다시 묻기
@pytest.mark.parametrize("answer, informative", [("", False), ("몰라요.", False), ("기억 안 나요", False), ("신났어요", True)])
def test_check_answer_endpoint(make_client, answer, informative):
    res = make_client().post(CHECK_URL, json={"answer": answer})
    assert res.status_code == 200
    assert res.json() == {"informative": informative}


def test_retry_request_asks_again_more_easily(make_client, question_body):
    body = {**question_body, "order": 1, "type": "EMOTION", "previousAnswers": [],
            "retry": {"question": "골을 넣은 순간, 기쁜 마음이 얼마나 컸니?", "answer": "몰라요"}}
    llm = FakeLLM({"question": "골을 넣었을 때 신났어, 아니면 떨렸어?"})
    res = make_client(llm).post(URL, json=body)
    assert res.json() == {"order": 1, "type": "EMOTION", "content": "골을 넣었을 때 신났어, 아니면 떨렸어?", "isFallback": False}
    prompt = llm.calls[0]["user_input"]
    assert "[다시 묻기]" in prompt
    assert "(이 답변에서 알 수 있는 정보 없음)" in prompt


def test_retry_rejects_same_question(make_client, question_body):
    same = "골을 넣은 순간, 기쁜 마음이 얼마나 컸니?"
    body = {**question_body, "order": 1, "type": "EMOTION", "previousAnswers": [], "retry": {"question": same, "answer": ""}}
    llm = FakeLLM({"question": same}, {"question": same})
    res = make_client(llm).post(URL, json=body)
    assert res.json()["isFallback"] is True
    assert res.json()["content"] == fallback_question(QuestionType.EMOTION, Emotion.JOY, retry=True)
    assert "되풀이" in llm.calls[1]["user_input"]


def test_retry_in_risk_mode_uses_gentle_fallback(make_client):
    body = {**_risk_body(order=1, qtype="EMOTION"), "retry": {"question": "지금은 마음이 어떠니?", "answer": "몰라요"}}
    res = make_client(llm=None).post(URL, json=body)
    assert res.json()["content"] == RISK_RETRY_FALLBACK


def test_retry_requires_question(make_client, question_body):
    body = {**question_body, "retry": {"question": "", "answer": "몰라요"}}
    res = make_client(FakeLLM()).post(URL, json=body)
    assert res.status_code == 422


@pytest.mark.parametrize("qtype", list(QuestionType))
@pytest.mark.parametrize("emotion", list(Emotion))
def test_every_retry_fallback_passes_rules(qtype, emotion):
    q = fallback_question(qtype, emotion, retry=True)
    assert validate_question(q) == q


def test_reason_risk_fallback_keeps_selected_emotion():
    assert fallback_question(QuestionType.REASON, Emotion.ANGER, risk=True).startswith("화난 마음이 들 수 있어")


def test_safety_rules_in_prompt():
    from app.question.prompts import INSTRUCTIONS
    assert "잘잘못은 어느 쪽으로도 판단하지 않는다" in INSTRUCTIONS
    assert "무서운 마음이 들 수 있어" in INSTRUCTIONS
    assert "그런 일이 있어서 무서웠구나" in INSTRUCTIONS


# 고른 감정과 일기가 어울리지 않을 때
def test_emotion_mismatch_rules_in_prompt():
    from app.question.prompts import INSTRUCTIONS
    assert "[고른 감정과 일기가 어울리지 않을 때]" in INSTRUCTIONS
    assert "골랐네" in INSTRUCTIONS
    assert "고른 감정이 틀렸다고 말하지 않는다" in INSTRUCTIONS


def test_mismatch_style_question_passes_rules():
    q = "친구랑 싸운 날 기쁨을 골랐네, 어떤 순간에 기쁜 마음이 들었어?"
    assert validate_question(q, diary="친구랑 싸웠어.") == q
