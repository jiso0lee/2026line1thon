# Swagger에 보여 줄 요청 예시, 실제 동작과 무관

_DIARY = "오늘 친구와 운동장에서 공놀이를 했다. 친구가 나에게 공을 넘겨줘서 골을 넣었다."

QUESTION_EXAMPLES = {
    "order1": {
        "summary": "1번째 질문 (EMOTION, 이전 답변 없음)",
        "value": {
            "emotion": "JOY",
            "content": _DIARY,
            "order": 1,
            "type": "EMOTION",
            "previousAnswers": [],
        },
    },
    "order2": {
        "summary": "2번째 질문 (REASON, 답변 1개) - 명세서 예시",
        "value": {
            "emotion": "JOY",
            "content": _DIARY,
            "order": 2,
            "type": "REASON",
            "previousAnswers": [
                {
                    "order": 1,
                    "type": "EMOTION",
                    "question": "골을 넣었을 때 어떤 기분이 들었니?",
                    "answer": "정말 신나고 친구한테 고마웠어요.",
                }
            ],
        },
    },
    "order3": {
        "summary": "3번째 질문 (PERSPECTIVE, 답변 2개 / 두 번째 답변 '몰라요')",
        "value": {
            "emotion": "JOY",
            "content": _DIARY,
            "order": 3,
            "type": "PERSPECTIVE",
            "previousAnswers": [
                {
                    "order": 1,
                    "type": "EMOTION",
                    "question": "골을 넣었을 때 어떤 기분이 들었니?",
                    "answer": "정말 신나고 친구한테 고마웠어요.",
                },
                {
                    "order": 2,
                    "type": "REASON",
                    "question": "친구가 공을 넘겨줬을 때 왜 고마운 마음이 들었니?",
                    "answer": "몰라요",
                },
            ],
        },
    },
    "invalid": {
        "summary": "잘못된 요청 예시 → 422 (order 2인데 type이 PERSPECTIVE)",
        "value": {
            "emotion": "JOY",
            "content": _DIARY,
            "order": 2,
            "type": "PERSPECTIVE",
            "previousAnswers": [],
        },
    },
}

_DISTRIBUTION = [
    {"emotion": "JOY", "count": 2, "ratio": 66.67},
    {"emotion": "SADNESS", "count": 1, "ratio": 33.33},
    {"emotion": "ANGER", "count": 0, "ratio": 0},
    {"emotion": "FEAR", "count": 0, "ratio": 0},
    {"emotion": "SURPRISE", "count": 0, "ratio": 0},
    {"emotion": "SHAME", "count": 0, "ratio": 0},
]

REPORT_EXAMPLES = {
    "normal": {
        "summary": "3일 동안 일기 3건 - 명세서 예시",
        "value": {
            "startDate": "2026-11-01",
            "endDate": "2026-11-03",
            "totalDiaryCount": 3,
            "distribution": _DISTRIBUTION,
            "days": [
                {"date": "2026-11-01", "emotions": ["JOY"]},
                {"date": "2026-11-02", "emotions": ["SADNESS"]},
                {"date": "2026-11-03", "emotions": ["JOY"]},
            ],
        },
    },
    "empty": {
        "summary": "일기 0건: AI 호출 없이 고정 문구",
        "value": {
            "startDate": "2026-11-01",
            "endDate": "2026-11-02",
            "totalDiaryCount": 0,
            "distribution": [{**item, "count": 0, "ratio": 0} for item in _DISTRIBUTION],
            "days": [
                {"date": "2026-11-01", "emotions": []},
                {"date": "2026-11-02", "emotions": []},
            ],
        },
    },
}
