import re

from app.errors import InvalidOutputError

MIN_LENGTH = 5
MAX_LENGTH = 80

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")
_MARKUP = re.compile(r"[*#`\[\]{}<>|\\]")

# 아이에게 보여 주면 안 되는 진단·비하 표현
BANNED_WORDS: tuple[str, ...] = (
    "우울증",
    "정신병",
    "정신과",
    "진단",
    "치료",
    "상담이 필요",
    "바보",
    "멍청",
    "한심",
    "못난",
    "나쁜 아이",
    "네 탓",
    "너 때문",
    "니 탓",
)

# 안전 모드에서 금지하는 질문 (가해자 관점, 아이 탓, 세부 내용 캐묻기, 참으라는 말)
_PERSON = r"(아빠|엄마|아버지|어머니|부모님?|친구|형|누나|언니|오빠|동생|선생님|삼촌|이모|고모|할머니|할아버지|그\s*사람|그\s*아이|상대)"
RISK_BANNED: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(_PERSON + r"[^?]{0,8}(왜|어떤\s*마음|무슨\s*마음|어떤\s*기분|어떤\s*생각|무슨\s*생각)"), "상대의 마음이나 이유를 묻는 질문"),
    (re.compile(r"왜\s*그랬|했길래|네가\s*(뭘|무엇을|어떻게)\s*했"), "아이 탓으로 돌릴 수 있는 질문"),
    (re.compile(r"잘못|나쁜\s*(행동|사람|짓)|나빴|나쁘다"), "잘잘못을 판단하는 표현"),
    (re.compile(r"때려|때렸|때린|맞아서|맞았을|괴롭혀|괴롭힌|따돌"), "사건을 사실처럼 되풀이하는 표현"),
    (re.compile(r"정말이야|진짜야|사실이야|거짓말"), "아이의 말을 의심하는 표현"),
    (re.compile(r"자세히|몇\s*번|언제부터|어떻게\s*(때|맞)"), "사건의 세부 내용을 캐묻는 질문"),
    (re.compile(r"참아야|참을\s*수|화해|용서|이해해\s*(줄|볼)"), "참거나 상대를 이해하라는 질문"),
)

_PARENT = re.compile(r"엄마|아빠|부모")
_HELP = re.compile(r"도와|도움|말해|말할|이야기해|이야기할")
_OTHER_ADULT = re.compile(r"선생님|어른|상담|다른\s*사람")

# 구체적인 장면으로 보기 어려운 흔한 낱말 (앞 두 글자 기준)
GENERIC_PREFIXES: frozenset[str] = frozenset(
    """
    오늘 어제 내일 그래 그리 그런 그때 그냥 정말 진짜 너무 엄청 많이 조금 처음 같이 함께
    나는 내가 나도 나를 나의 나에 나랑 너는 네가 너도 우리 저는 제가 했다 했어 했는 했고 하고 있었 있다 있어 없었 없다
    기분 마음 생각 느낌 기뻤 기쁘 기쁜 기뻐 슬펐 슬픈 슬퍼 화가 화났 화난 무서 놀랐 놀라 놀란
    부끄 좋았 좋아 좋은 싫었 싫어 재밌 재미 행복 신났 신나 그래서 그리고 하지만
    """.split()
)

_HANGUL_WORD = re.compile(r"[가-힣]{2,}")


# 일기에서 장면 낱말의 앞 두 글자 추출 (예: 운동장에서는 운동)
def scene_keys(diary: str) -> list[str]:
    keys: list[str] = []
    for word in _HANGUL_WORD.findall(diary):
        key = word[:2]
        if key not in GENERIC_PREFIXES and key not in keys:
            keys.append(key)
    return keys


# 재시도 안내에 보여 줄 일기 속 낱말
def scene_words(diary: str, limit: int = 5) -> list[str]:
    words: list[str] = []
    for word in _HANGUL_WORD.findall(diary):
        if word[:2] not in GENERIC_PREFIXES and word not in words:
            words.append(word)
    return words[:limit]


_QUOTES = "\"'“”‘’「」『』"


def clean_question(text: str) -> str:
    text = text.replace("？", "?").strip().strip(_QUOTES).strip()
    # "질문: ..." 같은 머리말 제거
    text = re.sub(r"^(질문|Q)\s*[:：]\s*", "", text)
    return text


# 질문 규칙 검사, 위반 시 InvalidOutputError 발생
# source_text: 일기 본문 + 앞선 답변, 아이가 직접 쓴 낱말은 금지어여도 허용
# diary: 일기 본문, 질문에 장면 낱말이 없으면 위반 (한국어 낱말이 없는 일기는 검사 생략)
# risk: 안전 모드, 장면 낱말 검사 대신 안전 원칙 검사
# previous_question: 다시 묻기일 때 직전 질문, 똑같이 되풀이하면 위반
def validate_question(
    text: str,
    source_text: str = "",
    diary: str = "",
    risk: bool = False,
    previous_question: str | None = None,
) -> str:
    question = clean_question(text)

    if "\n" in question or "\r" in question:
        raise InvalidOutputError("한 줄로 쓰지 않았음")
    if len(question) < MIN_LENGTH:
        raise InvalidOutputError("질문이 너무 짧음")
    if len(question) > MAX_LENGTH:
        raise InvalidOutputError(f"질문이 너무 김({len(question)}자). {MAX_LENGTH}자 이하로 줄일 것")
    if not _HANGUL.search(question):
        raise InvalidOutputError("한국어가 아님")
    if _LATIN.search(question):
        raise InvalidOutputError("영어나 감정 코드가 들어 있음")
    if _MARKUP.search(question):
        raise InvalidOutputError("특수 기호·마크다운이 들어 있음")
    if not question.endswith("?"):
        raise InvalidOutputError("물음표로 끝나지 않음")
    if question.count("?") != 1:
        raise InvalidOutputError("질문이 2개 이상임. 질문은 하나만")
    for word in BANNED_WORDS:
        if word in question and word not in source_text:
            raise InvalidOutputError(f"아이에게 부적절한 표현 '{word}' 사용")

    if previous_question is not None and question == clean_question(previous_question):
        raise InvalidOutputError("방금 질문을 그대로 되풀이함. 더 쉬운 말로 바꿔 물을 것")

    if risk:
        for pattern, reason in RISK_BANNED:
            if pattern.search(question):
                raise InvalidOutputError(f"안전 모드 위반: {reason}")
        if _PARENT.search(question) and _HELP.search(question) and not _OTHER_ADULT.search(question):
            raise InvalidOutputError("안전 모드 위반: 도움 요청 대상을 부모로만 정함, 선생님 등 다른 어른도 함께 제시할 것")
        return question

    keys = scene_keys(diary)
    if keys and not any(key in question for key in keys):
        hint = ", ".join(scene_words(diary))
        raise InvalidOutputError(f"일기 속 구체적인 장면이 질문에 없음. 일기의 낱말(예: {hint})을 넣어서 물을 것")
    return question
