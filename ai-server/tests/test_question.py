import pytest

from app.domain import Emotion, QuestionType
from app.errors import InvalidOutputError, LLMError
from app.question.answers import is_uninformative
from app.question.fallback import fallback_question
from app.question.validator import validate_question
from tests.conftest import FakeLLM

URL = "/api/diary-questions/generate"

# 정상 흐름
def test_generates_question_with_spec_shape(make_client, question_body):
    llm = FakeLLM({"question": "친구가 공을 넘겨줬을 때 왜 고마운 마음이 들었니?"})
    res = make_client(llm).post(URL, json=question_body)

    assert res.status_code == 200
    assert res.json() == {
        "order": 2,
        "type": "REASON",
        "content": "친구가 공을 넘겨줬을 때 왜 고마운 마음이 들었니?",
        "isFallback": False,
    }
    # 프롬프트에 일기·이전 답변·선택 감정 포함 확인
    prompt = llm.calls[0]["user_input"]
    assert "기쁨" in prompt and "공놀이" in prompt and "고마웠어요" in prompt


def test_first_question_with_empty_previous_answers(make_client, question_body):
    body = {**question_body, "order": 1, "type": "EMOTION", "previousAnswers": []}
    res = make_client(FakeLLM({"question": "골을 넣었을 때 기분이 어땠니?"})).post(URL, json=body)
    assert res.status_code == 200
    assert res.json()["order"] == 1 and res.json()["isFallback"] is False

# 재시도·기본 질문
def test_retries_when_output_breaks_rules(make_client, question_body):
    llm = FakeLLM(
        {"question": "기분이 어땠니? 그리고 친구는 어땠니?"},  # 질문 2개라 규칙 위반
        {"question": "친구가 공을 넘겨줬을 때 어떤 생각이 들었니?"},
    )
    res = make_client(llm).post(URL, json=question_body)
    assert res.json()["isFallback"] is False
    assert len(llm.calls) == 2
    assert "질문이 2개 이상" in llm.calls[1]["user_input"]  # 두 번째 시도에 위반 이유 전달


def test_falls_back_after_repeated_failure(make_client, question_body):
    llm = FakeLLM({"question": "JOY를 느꼈니?"}, LLMError("timeout"))
    res = make_client(llm).post(URL, json=question_body)
    assert res.status_code == 200
    assert res.json() == {
        "order": 2,
        "type": "REASON",
        "content": "왜 그런 기분이 들었다고 생각하나요?",
        "isFallback": True,
    }


def test_falls_back_without_openai_key(make_client, question_body):
    res = make_client(llm=None).post(URL, json=question_body)
    assert res.status_code == 200 and res.json()["isFallback"] is True


@pytest.mark.parametrize("emotion", list(Emotion))
@pytest.mark.parametrize("qtype", list(QuestionType))
def test_every_fallback_question_passes_rules(emotion, qtype):
    assert validate_question(fallback_question(qtype, emotion)) == fallback_question(qtype, emotion)

# 잘못된 요청 (order/type)
@pytest.mark.parametrize(
    "patch, expected",
    [
        ({"type": "PERSPECTIVE"}, "order 2의 type은 REASON"),
        ({"previousAnswers": []}, "previousAnswers가 1개"),
        ({"order": 4}, "order"),
        ({"emotion": "HAPPY"}, "emotion"),
        ({"content": "   "}, "content"),
    ],
)
def test_rejects_invalid_requests(make_client, question_body, patch, expected):
    llm = FakeLLM()
    res = make_client(llm).post(URL, json={**question_body, **patch})
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert any(expected in d for d in error["details"])
    assert llm.calls == []  # 잘못된 요청에는 LLM을 부르지 않음


def test_rejects_previous_answers_in_wrong_order(make_client, question_body):
    body = {**question_body, "order": 3, "type": "PERSPECTIVE"}
    body["previousAnswers"] = [
        {"order": 2, "type": "REASON", "question": "왜?", "answer": "몰라"},
        {"order": 1, "type": "EMOTION", "question": "기분은?", "answer": "좋아"},
    ]
    res = make_client(FakeLLM()).post(URL, json=body)
    assert res.status_code == 422

# '몰라요' 답변
@pytest.mark.parametrize(
    "answer", ["", "   ", None, "몰라요", "모르겠어요.", "잘 모르겠어요", "글쎄요...", "기억 안 나요", "그냥요", "없어요", "음...", "ㅇㅇ"]
)
def test_uninformative_answers(answer):
    assert is_uninformative(answer) is True


@pytest.mark.parametrize("answer", ["신났어요", "몰라요 그냥 좋았어요", "친구가 없어서 심심했어요", "안 좋았어", "응 기뻤어"])
def test_informative_answers(answer):
    assert is_uninformative(answer) is False


def test_uninformative_answer_is_marked_in_prompt(make_client, question_body):
    question_body["previousAnswers"][0]["answer"] = "몰라요"
    llm = FakeLLM({"question": "공을 받았을 때 어떤 생각이 들었니?"})
    make_client(llm).post(URL, json=question_body)
    prompt = llm.calls[0]["user_input"]
    assert "(이 답변에서 알 수 있는 정보 없음)" in prompt
    assert "몰라요" not in prompt

# 출력 검증
@pytest.mark.parametrize(
    "text",
    [
        "기분이 어땠니",  # 물음표 없음
        "기분은? 이유는?",  # 질문 2개
        "How did you feel?",  # 영어
        "**기분**이 어땠니?",  # 마크다운
        "혹시 우울증이 있는 건 아닐까?",  # 진단
        "가" * 90 + "?",  # 너무 김
    ],
)
def test_validator_rejects(text):
    with pytest.raises(InvalidOutputError):
        validate_question(text)


def test_validator_cleans_quotes_and_fullwidth_mark():
    assert validate_question('"골을 넣었을 때 기분이 어땠니？"') == "골을 넣었을 때 기분이 어땠니?"


def test_banned_word_allowed_when_child_wrote_it():
    q = "치과에서 치료받을 때 어떤 마음이었니?"
    with pytest.raises(InvalidOutputError):
        validate_question(q)
    assert validate_question(q, source_text="오늘 치과에서 치료를 받았다.") == q


def test_api_key_required_when_configured(make_client, question_body):
    client = make_client(FakeLLM({"question": "골을 넣었을 때 기분이 어땠니?"}), ai_api_key="secret")
    assert client.post(URL, json=question_body).status_code == 401
    res = client.post(URL, json=question_body, headers={"X-API-Key": "secret"})
    assert res.status_code == 200


def test_health(make_client):
    assert make_client().get("/health").json()["status"] == "ok"

# 일기 속 장면
DIARY = "오늘 친구와 운동장에서 공놀이를 했다. 친구가 나에게 공을 넘겨줘서 골을 넣었다."


def test_generic_question_without_diary_scene_is_rejected():
    with pytest.raises(InvalidOutputError, match="일기 속 구체적인 장면"):
        validate_question("그 기쁨이 몸이나 마음에서 어떻게 느껴졌어?", diary=DIARY)


@pytest.mark.parametrize(
    "question",
    [
        "친구가 준 공으로 골을 넣은 순간, 기쁜 마음이 얼마나 컸니?",
        "운동장에서 뛰어놀 때 어떤 생각이 들었니?",
        "공놀이를 함께한 친구는 그때 어떤 마음이었을까?",
    ],
)
def test_question_with_diary_scene_passes(question):
    assert validate_question(question, diary=DIARY) == question


def test_scene_check_skipped_when_diary_has_no_korean_words():
    assert validate_question("오늘 어떤 일이 있었니?", diary="string")


def test_retry_feedback_names_diary_words(make_client, question_body):
    llm = FakeLLM(
        {"question": "그 기쁨이 몸이나 마음에서 어떻게 느껴졌어?"},
        {"question": "친구가 공을 넘겨줬을 때 왜 고마운 마음이 들었니?"},
    )
    res = make_client(llm).post(URL, json=question_body)
    assert res.json()["isFallback"] is False
    assert "운동장에서" in llm.calls[1]["user_input"]  # 재시도 안내에 일기 낱말 예시 포함


def test_prompt_requires_diary_scene(make_client, question_body):
    llm = FakeLLM({"question": "친구가 공을 넘겨줬을 때 왜 고마운 마음이 들었니?"})
    make_client(llm).post(URL, json=question_body)
    assert "일기 속 구체적인 장면" in llm.calls[0]["instructions"]
