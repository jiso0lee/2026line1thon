from app.domain import EMOTION_MIND, EMOTION_WHEN, Emotion, QuestionType


# 안전 모드 기본 질문 (잘잘못 판단 금지, 세부 내용 캐묻지 않기, 부모 외 어른도 제시)
def risk_fallback(question_type: QuestionType, emotion: Emotion) -> str:
    if question_type is QuestionType.EMOTION:
        return "솔직하게 이야기해 줘서 고마워, 지금은 마음이 어떠니?"
    if question_type is QuestionType.REASON:
        return f"{EMOTION_MIND[emotion]}이 들 수 있어, 지금 무엇이 있으면 마음이 조금 편해질까?"
    return "무섭거나 위험할 때는 선생님이나 믿을 수 있는 어른에게 말해도 돼, 지금 떠오르는 어른이 있니?"


# 안전 모드에서 다시 묻기 기본 질문
RISK_RETRY_FALLBACK = "말하기 어려우면 괜찮아, 지금 곁에서 너를 도와줄 수 있는 선생님이나 어른이 있니?"


# LLM을 쓸 수 없을 때 돌려주는 질문 유형별 기본 질문
# risk: 안전 모드, retry: 쉬운 말로 다시 묻기
def fallback_question(question_type: QuestionType, emotion: Emotion, risk: bool = False, retry: bool = False) -> str:
    if risk:
        return RISK_RETRY_FALLBACK if retry else risk_fallback(question_type, emotion)
    if retry:
        if question_type is QuestionType.EMOTION:
            return f"그때 {EMOTION_MIND[emotion]}이 아주 컸니, 아니면 조금이었니?"
        if question_type is QuestionType.REASON:
            return "그 일에서 어떤 순간이 가장 기억에 남니?"
        return "다음에 비슷한 일이 생기면 어떻게 하고 싶니?"
    if question_type is QuestionType.EMOTION:
        return f"{EMOTION_WHEN[emotion]} 마음속에서 어떤 느낌이 들었니?"
    if question_type is QuestionType.REASON:
        return f"어떤 일 때문에 {EMOTION_MIND[emotion]}이 들었을까?"
    return "친구가 같은 일을 겪었다면, 너는 친구에게 어떤 말을 해 주고 싶니?"
