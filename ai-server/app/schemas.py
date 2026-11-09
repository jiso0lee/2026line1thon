from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain import ORDER_TO_TYPE, Emotion, QuestionType


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

# 질문 생성
class PreviousAnswer(_Base):
    order: int = Field(ge=1, le=3)
    type: QuestionType
    question: str = Field(min_length=1, max_length=500)
    # 비어 있거나 "몰라요"인 답변도 허용
    answer: str | None = Field(default="", max_length=3000)

    @field_validator("answer", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return "" if v is None else v


class QuestionRequest(_Base):
    emotion: Emotion
    content: str = Field(min_length=1, max_length=5000, description="사용자가 수정/확인한 일기 텍스트")
    order: int = Field(ge=1, le=3)
    type: QuestionType
    previous_answers: list[PreviousAnswer] = Field(default_factory=list, alias="previousAnswers")

    @model_validator(mode="after")
    def _check_order_and_history(self):
        expected_type = ORDER_TO_TYPE[self.order]
        if self.type != expected_type:
            raise ValueError(
                f"order {self.order}의 type은 {expected_type.value}이어야 합니다. (받은 값: {self.type.value})"
            )
        if len(self.previous_answers) != self.order - 1:
            raise ValueError(
                f"order {self.order} 요청에는 previousAnswers가 {self.order - 1}개 있어야 합니다. "
                f"(받은 개수: {len(self.previous_answers)})"
            )
        for index, item in enumerate(self.previous_answers, start=1):
            if item.order != index or item.type != ORDER_TO_TYPE[index]:
                raise ValueError(
                    f"previousAnswers[{index - 1}]는 order {index}, type {ORDER_TO_TYPE[index].value}이어야 합니다."
                )
        return self


class QuestionResponse(_Base):
    order: int
    type: QuestionType
    content: str
    is_fallback: bool = Field(alias="isFallback")

# 감정 리포트
class DistributionItem(_Base):
    emotion: Emotion
    count: int = Field(ge=0)
    ratio: float = Field(ge=0, le=100)


class DayRecord(_Base):
    date: date
    emotions: list[Emotion] = Field(default_factory=list)


class ReportRequest(_Base):
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    total_diary_count: int = Field(ge=0, alias="totalDiaryCount")
    distribution: list[DistributionItem]
    days: list[DayRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_consistency(self):
        if self.end_date < self.start_date:
            raise ValueError("endDate는 startDate보다 빠를 수 없습니다.")

        emotions = [item.emotion for item in self.distribution]
        if len(emotions) != len(Emotion) or set(emotions) != set(Emotion):
            raise ValueError("distribution에는 감정 6종이 각각 한 번씩 있어야 합니다. (0건 포함)")

        total = sum(item.count for item in self.distribution)
        if total != self.total_diary_count:
            raise ValueError(
                f"distribution count 합계({total})와 totalDiaryCount({self.total_diary_count})가 다릅니다."
            )

        previous: date | None = None
        for day in self.days:
            if not (self.start_date <= day.date <= self.end_date):
                raise ValueError(f"days의 날짜 {day.date}가 조회 기간 밖에 있습니다.")
            if previous is not None and day.date <= previous:
                raise ValueError("days는 날짜순으로, 날짜 중복 없이 전달해야 합니다.")
            previous = day.date
        return self


class ReportResponse(BaseModel):
    most_emotion_reason: str
    least_emotion_reason: str
    parent_advice: str
    trend_interpretation: str

# 공통 오류 응답
class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody