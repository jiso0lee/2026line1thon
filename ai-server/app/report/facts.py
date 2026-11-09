from dataclasses import dataclass
from datetime import date

from app.domain import EMOTION_NAME, EMOTION_ORDER, Emotion
from app.schemas import DistributionItem, ReportRequest


@dataclass(frozen=True)
class ReportFacts:
    total: int
    period_days: int
    most: list[DistributionItem]  # 가장 많은 감정 (동률 모두), 0건이면 빈 리스트
    least: list[DistributionItem]  # 가장 적은 감정 (0건·동률 모두)
    all_equal: bool  # 6개 감정 건수가 모두 같음
    sequence: list[tuple[date, Emotion]]  # 감정을 기록한 날만 날짜순
    few_records: bool


# 받은 count로 최다·최소 감정만 정리, 수치는 다시 계산하지 않음
def build_facts(request: ReportRequest, few_records_threshold: int) -> ReportFacts:
    by_emotion = {item.emotion: item for item in request.distribution}
    items = [by_emotion[emotion] for emotion in EMOTION_ORDER]

    max_count = max(item.count for item in items)
    min_count = min(item.count for item in items)

    most = [item for item in items if item.count == max_count] if max_count > 0 else []
    least = [item for item in items if item.count == min_count]

    sequence = [(day.date, emotion) for day in request.days for emotion in day.emotions]

    return ReportFacts(
        total=request.total_diary_count,
        period_days=(request.end_date - request.start_date).days + 1,
        most=most,
        least=least,
        all_equal=max_count == min_count,
        sequence=sequence,
        few_records=request.total_diary_count < few_records_threshold,
    )


def names(items: list[DistributionItem]) -> str:
    return ", ".join(EMOTION_NAME[item.emotion] for item in items)


# 받은 비율을 그대로 표기 (66.67은 66.67, 50.0은 50)
def format_ratio(ratio: float) -> str:
    return f"{ratio:.2f}".rstrip("0").rstrip(".")
