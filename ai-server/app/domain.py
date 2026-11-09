from enum import Enum


class Emotion(str, Enum):
    JOY = "JOY"
    SADNESS = "SADNESS"
    ANGER = "ANGER"
    FEAR = "FEAR"
    SURPRISE = "SURPRISE"
    SHAME = "SHAME"


class QuestionType(str, Enum):
    EMOTION = "EMOTION"
    REASON = "REASON"
    PERSPECTIVE = "PERSPECTIVE"


# 질문 순서별 질문 유형
ORDER_TO_TYPE: dict[int, QuestionType] = {
    1: QuestionType.EMOTION,
    2: QuestionType.REASON,
    3: QuestionType.PERSPECTIVE,
}

QUESTION_TYPE_LABEL: dict[QuestionType, str] = {
    QuestionType.EMOTION: "감정 탐색",
    QuestionType.REASON: "이유 탐색",
    QuestionType.PERSPECTIVE: "관점 확장",
}

# 감정 코드별 표시 이름
EMOTION_NAME: dict[Emotion, str] = {
    Emotion.JOY: "기쁨",
    Emotion.SADNESS: "슬픔",
    Emotion.ANGER: "화남",
    Emotion.FEAR: "무서움",
    Emotion.SURPRISE: "놀람",
    Emotion.SHAME: "부끄러움",
}

# 기본 질문 문장용 감정 활용형
EMOTION_WHEN: dict[Emotion, str] = {
    Emotion.JOY: "기뻤을 때",
    Emotion.SADNESS: "슬펐을 때",
    Emotion.ANGER: "화가 났을 때",
    Emotion.FEAR: "무서웠을 때",
    Emotion.SURPRISE: "놀랐을 때",
    Emotion.SHAME: "부끄러웠을 때",
}

EMOTION_MIND: dict[Emotion, str] = {
    Emotion.JOY: "기쁜 마음",
    Emotion.SADNESS: "슬픈 마음",
    Emotion.ANGER: "화난 마음",
    Emotion.FEAR: "무서운 마음",
    Emotion.SURPRISE: "놀란 마음",
    Emotion.SHAME: "부끄러운 마음",
}

# 6종 감정의 고정 순서
EMOTION_ORDER: list[Emotion] = list(Emotion)
