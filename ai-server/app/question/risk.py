import re

# 위험 내용 신호 (폭력, 학대, 괴롭힘, 자해, 성적 피해, 위협, 방임)
# 놓치는 표현은 LLM 판단(risk 필드)으로 한 번 더 잡음
RISK_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p)
    for p in (
        r"때리|때렸|때려|때린",
        r"(한테|에게|한테서|에게서)\s*맞",
        r"발로\s*(차|찼)|밀쳤|밀쳐|목을\s*졸",
        r"폭력|폭행|학대|학폭",
        r"괴롭|따돌|왕따|은따",
        r"협박|죽여\s*버|죽인다고|죽일\s*거",
        r"죽고\s*싶|죽을래|죽어\s*버리고|자해|자살|사라지고\s*싶|없어지고\s*싶|살기\s*싫|태어나지\s*말",
        r"성추행|성폭력|몸을\s*만지|만지지\s*말라|아무(한테|에게)도\s*말하지\s*말|비밀로\s*하라",
        r"밥을?\s*안\s*줘|밥을?\s*못\s*먹게|집에서\s*쫓겨|가뒀|가둬",
    )
)


def detect_risk(*texts: str | None) -> bool:
    joined = "\n".join(t for t in texts if t)
    return any(p.search(joined) for p in RISK_PATTERNS)
