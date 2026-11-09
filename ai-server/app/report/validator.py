import re
from datetime import timedelta

from app.errors import InvalidOutputError
from app.report.facts import ReportFacts, format_ratio
from app.report.prompts import ReportLLMOutput
from app.schemas import ReportRequest, ReportResponse

# 필드별 (최소 문장 수, 최대 문장 수, 최대 글자 수)
FIELD_RULES: dict[str, tuple[int, int, int]] = {
    "most_emotion_reason": (1, 2, 160),
    "least_emotion_reason": (1, 2, 160),
    "parent_advice": (1, 1, 120),
    "trend_interpretation": (1, 2, 180),
}

# 진단·단정 표현
BANNED_WORDS: tuple[str, ...] = (
    "우울",
    "불안장애",
    "장애",
    "진단",
    "치료",
    "정신건강",
    "정신과",
    "상담이 필요",
    "좋아졌",
    "나빠졌",
    "개선",
    "악화",
    "호전",
    "문제가 있",
    "위험",
)

# least_emotion_reason에서 '느끼지 않았다'고 단정하는 표현
LEAST_BANNED: tuple[str, ...] = (
    "느끼지 않았",
    "느끼지 않은",
    "느끼지 못했",
    "느끼지 못한",
    "전혀 느끼지",
    "느낀 적이 없",
    "느낀 적 없",
)

_LATIN = re.compile(r"[A-Za-z]")
_MARKUP = re.compile(r"[*#`\[\]{}<>|\\]")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


def _count_sentences(text: str) -> int:
    count = len(_SENTENCE_END.findall(text))
    if not _SENTENCE_END.search(text[-1:] if text else ""):
        count += 1  # 마침표 없이 끝난 마지막 문장
    return count


def _allowed_numbers(request: ReportRequest, facts: ReportFacts) -> set[str]:
    allowed: set[str] = {str(facts.total), str(facts.period_days), "6"}
    for item in request.distribution:
        allowed.add(str(item.count))
        allowed.add(format_ratio(item.ratio))
        allowed.add(f"{item.ratio:.2f}")
    allowed.add(str(len(facts.most)))
    allowed.add(str(len(facts.least)))
    recorded_days = len({d for d, _ in facts.sequence})
    allowed.update({str(recorded_days), str(facts.period_days - recorded_days)})

    current = request.start_date
    while current <= request.end_date:
        allowed.update({str(current.year), str(current.month), str(current.day)})
        allowed.update({f"{current.month:02d}", f"{current.day:02d}"})
        current += timedelta(days=1)
    return allowed


# 리포트 문구 규칙 검사, 위반 시 InvalidOutputError 발생
def validate_report(output: ReportLLMOutput, request: ReportRequest, facts: ReportFacts) -> ReportResponse:
    allowed = _allowed_numbers(request, facts)
    cleaned: dict[str, str] = {}

    for field, (min_s, max_s, max_len) in FIELD_RULES.items():
        text = " ".join(getattr(output, field).split())  # 줄바꿈·중복 공백 정리
        if not text:
            raise InvalidOutputError(f"{field}가 비어 있음")
        if len(text) > max_len:
            raise InvalidOutputError(f"{field}가 너무 김({len(text)}자). {max_len}자 이하로")
        if _LATIN.search(text):
            raise InvalidOutputError(f"{field}에 영어나 감정 코드가 들어 있음")
        if _MARKUP.search(text):
            raise InvalidOutputError(f"{field}에 특수 기호·마크다운이 들어 있음")
        sentences = _count_sentences(text)
        if not (min_s <= sentences <= max_s):
            raise InvalidOutputError(f"{field}는 {min_s}~{max_s}문장이어야 함(현재 {sentences}문장)")
        for word in BANNED_WORDS:
            if word in text:
                raise InvalidOutputError(f"{field}에 진단·단정 표현 '{word}' 사용")
        for number in _NUMBER.findall(text):
            if number not in allowed:
                raise InvalidOutputError(f"{field}에 기록에 없는 숫자 '{number}' 사용. 받은 숫자를 그대로 쓸 것")
        cleaned[field] = text

    for phrase in LEAST_BANNED:
        if phrase in cleaned["least_emotion_reason"]:
            raise InvalidOutputError(f"least_emotion_reason에서 '{phrase}'처럼 느끼지 않았다고 단정함")

    return ReportResponse(**cleaned)
