import re

_TOKEN = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣA-Za-z0-9]+")

# 정보 없음 낱말
_NO_INFO_TOKEN = re.compile(
    r"""
    (잘)?(몰라|모르|몰루|모름)[가-힣]{0,4}   # 몰라, 몰라요, 모르겠어요, 잘몰라 ...
    | 글쎄[가-힣]{0,2}                     # 글쎄, 글쎄요
    | 그냥[가-힣]{0,1}                     # 그냥, 그냥요
    | 없[어음다는었][가-힣]{0,3}            # 없어, 없어요, 없음, 없는데
    | 기억(이|도|은)?                       # '기억 안 나요'의 '기억'
    | 생각(이|도|은)?                       # '생각 안 나요'의 '생각'
    | 안(나|남|나요|나는데|떠올라|떠올라요)?  # '안', '안나요'
    | 나(요|는데)?                          # '안 나요'의 '나요'
    | 떠오르지 | 않아(요)?
    | 잘 | 별로 | 딱히 | 아무(것도|거나|거도)?
    | 음+ | 어+ | 흠+ | 으음+ | 엄+
    | [ㅇㄴㅁ]+                              # ㅇㅇ, ㄴㄴ, ㅁㄹ
    | [ㅋㅎㅠㅜ]+
    """,
    re.VERBOSE,
)


# 모든 낱말이 정보 없음 낱말일 때만 정보 없는 답변 (예: 빈 답변, 몰라요, 기억 안 나요)
def is_uninformative(answer: str | None) -> bool:
    if answer is None:
        return True
    tokens = _TOKEN.findall(answer)
    if not tokens:
        return True
    return all(_NO_INFO_TOKEN.fullmatch(token) for token in tokens)
