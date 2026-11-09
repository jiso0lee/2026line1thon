from datetime import date

from pydantic import BaseModel, Field

from app.domain import EMOTION_NAME, EMOTION_ORDER
from app.report.facts import ReportFacts, format_ratio, names
from app.schemas import ReportRequest


# LLM 응답 JSON 형식, API 응답 필드와 동일
class ReportLLMOutput(BaseModel):
    most_emotion_reason: str = Field(description="가장 자주 기록한 감정 설명, 1~2문장")
    least_emotion_reason: str = Field(description="가장 적게 기록한 감정 설명, 1~2문장")
    parent_advice: str = Field(description="보호자에게 드리는 구체적인 조언, 1문장")
    trend_interpretation: str = Field(description="날짜별 감정 기록의 변화 설명, 1~2문장")


INSTRUCTIONS = """\
너는 어린이 감정 일기 서비스에서 보호자에게 아이의 감정 기록을 설명해 주는 도우미야.
아래 [기록 요약]만 근거로 네 가지 문구를 한국어 존댓말(~해요 체)로 쓴다.

[모든 문구 공통 규칙]
1. 전달받은 기록에만 근거한다. 기록에 없는 사건·원인·아이의 상태를 추측하지 않는다.
2. 통계 수치를 다시 계산하거나 바꾸지 않는다. 숫자를 쓸 때는 [기록 요약]에 있는 숫자를 그대로 쓴다. (반올림·'약' 표기 금지)
3. 정신건강 진단을 하지 않고, 감정이 '좋아졌다/나빠졌다', '개선/악화'처럼 단정하지 않는다.
4. 기록이 적으면 장기적인 변화가 있다고 해석하지 않는다.
5. 감정 이름은 기쁨·슬픔·화남·무서움·놀람·부끄러움으로 쓰고, 영어나 감정 코드(JOY 등)는 쓰지 않는다.
6. 마크다운, 이모지, 따옴표, 줄바꿈을 쓰지 않는다.

[문구별 규칙]
- most_emotion_reason: 가장 자주 기록한 감정 설명. 동률이면 모두 언급한다. 1~2문장.
- least_emotion_reason: 가장 적게 기록한 감정 설명. 0건인 감정과 동률인 감정을 모두 언급한다. 1~2문장.
  기록되지 않은 감정을 '느끼지 않았다'고 단정하지 말고, '기록되지 않았다/적게 기록했다'고 표현한다.
- parent_advice: 보호자가 아이와 함께 해 볼 수 있는 구체적인 행동 하나를 제안하는 1문장.
  기록된 감정과 연결하되, 원인을 추측하거나 진단·치료를 권하지 않는다.
- trend_interpretation: 날짜별 감정 기록이 어떤 순서로 이어졌는지 설명. 1~2문장.
  [기록 양]이 '적음'이면 이 기록만으로 장기적인 변화를 판단하기 어렵다는 점을 함께 밝힌다.

결과는 위 네 필드를 가진 JSON 객체로만 돌려준다.
"""


def _korean_date(value: date) -> str:
    return f"{value.month}월 {value.day}일"


def build_user_input(request: ReportRequest, facts: ReportFacts, retry_feedback: str | None = None) -> str:
    by_emotion = {item.emotion: item for item in request.distribution}
    distribution_text = ", ".join(
        f"{EMOTION_NAME[e]} {by_emotion[e].count}건({format_ratio(by_emotion[e].ratio)}%)" for e in EMOTION_ORDER
    )

    if facts.all_equal:
        most_text = f"모든 감정을 같은 횟수({facts.most[0].count}건)로 기록함"
        least_text = "모든 감정을 같은 횟수로 기록해 가장 적은 감정을 따로 고를 수 없음"
    else:
        most_text = f"{names(facts.most)} ({facts.most[0].count}건)"
        least_text = f"{names(facts.least)} ({facts.least[0].count}건)"

    if facts.sequence:
        sequence_text = " → ".join(f"{_korean_date(d)} {EMOTION_NAME[e]}" for d, e in facts.sequence)
    else:
        sequence_text = "없음"

    recorded_days = len({d for d, _ in facts.sequence})
    amount = f"적음 ({facts.total}건)" if facts.few_records else f"충분함 ({facts.total}건)"

    lines = [
        "[기록 요약]",
        f"- 조회 기간: {_korean_date(request.start_date)} ~ {_korean_date(request.end_date)} ({facts.period_days}일)",
        f"- 완료된 일기 수: {facts.total}건",
        f"- 감정별 기록: {distribution_text}",
        f"- 가장 많이 기록한 감정: {most_text}",
        f"- 가장 적게 기록한 감정: {least_text}",
        f"- 날짜별 기록 순서: {sequence_text}",
        f"- 일기를 쓴 날: {recorded_days}일 / 쓰지 않은 날: {facts.period_days - recorded_days}일",
        f"- 기록 양: {amount}",
    ]
    if retry_feedback:
        lines.append("")
        lines.append(f"[주의] 방금 만든 문구는 규칙을 어겼어: {retry_feedback}. 규칙을 지켜서 다시 만들어 줘.")
    return "\n".join(lines)
