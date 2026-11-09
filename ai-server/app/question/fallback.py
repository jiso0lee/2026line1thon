from app.domain import EMOTION_MIND, EMOTION_WHEN, Emotion, QuestionType


# LLM을 쓸 수 없을 때 돌려주는 질문 유형별 기본 질문
def fallback_question(question_type: QuestionType, emotion: Emotion) -> str:
    if question_type is QuestionType.EMOTION:
        return f"{EMOTION_WHEN[emotion]} 마음속에서 어떤 느낌이 들었니?"
    if question_type is QuestionType.REASON:
        return f"어떤 일 때문에 {EMOTION_MIND[emotion]}이 들었을까?"
    return "친구가 같은 일을 겪었다면, 너는 친구에게 어떤 말을 해 주고 싶니?"
