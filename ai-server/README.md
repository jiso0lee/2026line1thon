# 생각의힘 AI 서버

백엔드가 호출하는 AI 서버

DB 없이 요청을 받아 결과만 리턴

| API | 호출 | 하는 일 |
| --- | --- | --- |
| `POST /api/diary-questions/generate` | BE1 -> AI | 일기 + 이전 답변을 보고 질문 1개 생성 (`retry`가 있으면 같은 질문을 쉬운 말로 다시 묻기) |
| `POST /api/diary-answers/check` | BE1 -> AI | 답변이 빈 답변이나 "몰라요"처럼 정보가 없는지 확인 (LLM 호출 없음) |
| `POST /api/emotion-reports/generate` | BE2 -> AI | 기간 통계를 보고 설명 문구 4개 생성 |
| `GET /health` | 배포 환경 | 상태 확인 (인증 없음) |
| `GET /docs` | 사람 | Swagger |

## 폴더 구조

```
app/
  main.py            FastAPI 앱, 라우트, 오류 응답 형식
  config.py          환경변수 설정
  domain.py          감정 코드, 질문 유형, 순서
  schemas.py         요청/응답 JSON 형식 + 요청 검증
  errors.py          서버 내부 예외
  examples.py        Swagger 요청 예시 (아직 어느 파일에도 연결 안 됨)
  llm.py             OpenAI 호출 (Responses API + Structured Outputs)
  question/          질문 생성: 프롬프트, '몰라요' 판별, 위험 내용 감지, 출력 검증, 기본 질문
  report/            리포트: 최다/최소 정리, 프롬프트, 출력 검증
tests/               pytest (OpenAI 없이 가짜 LLM으로 테스트)
scripts/try_live.py  실제 OpenAI로 품질 확인
```

## 로컬 실행 (Mac)

```bash
# 1) Python 3.13 설치 (둘 중 하나)
brew install python@3.13
#   또는  curl -LsSf https://astral.sh/uv/install.sh | sh && uv python install 3.13

# 2) 가상환경 + 패키지
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 3) 환경변수
cp .env.example .env

# 4) 실행 → http://localhost:8000/docs
uvicorn app.main:app --reload --env-file .env
```

- 테스트: `pytest -q`
- 실제 질문 품질 확인: `python -m scripts.try_live` (리포트는 `--report`)
- 가상환경을 켠 뒤에도 `python --version`이 3.13이 아니면 `unalias python` 실행 후 다시 확인

## Docker

```bash
docker build -t saenggak-ai .
docker run --rm --env-file .env -p 8000:8000 saenggak-ai
```

M 시리즈 Mac에서 만든 이미지를 x86 서버에 올릴 때는 `docker build --platform linux/amd64 -t saenggak-ai .`로 빌드해야 함

## BE가 알아야 할 응답 규칙

### 질문 생성

```json
// 200 OK
{ "order": 2, "type": "REASON", "content": "친구가 공을 넘겨줬을 때 왜 고마운 마음이 들었니?", "isFallback": false }
```

- `isFallback: true`면 AI가 질문을 만들지 못해 기본 질문을 돌려준 것, 이때도 200 응답
- 요청이 명세와 다르면 `422` 응답
- 답변이 비어 있거나 "몰라요"처럼 정보가 없으면 그 답변은 근거로 쓰지 않고 일기 본문을 바탕으로 질문함

#### 빈 답변, "몰라요" 답변 다시 묻기

아이가 빈 답변이나 "몰라요"를 내면 같은 질문을 쉬운 말로 한 번 더 묻고, 또 같은 답이면 다음 질문으로 넘어감

1) 답변을 받으면 `POST /api/diary-answers/check`로 확인

```json
// 요청
{ "answer": "몰라요" }
// 200 OK
{ "informative": false }
```

2) `informative: false`이고 이 order를 아직 다시 묻지 않았으면, 같은 order로 질문 생성 API를 다시 호출하고 `retry`에 방금 질문과 답변을 넣음

```json
{
  "emotion": "JOY",
  "content": "오늘 친구와 운동장에서 공놀이를 했다. 친구가 나에게 공을 넘겨줘서 골을 넣었다.",
  "order": 1,
  "type": "EMOTION",
  "previousAnswers": [],
  "retry": { "question": "골을 넣은 순간, 기쁜 마음이 얼마나 컸니?", "answer": "몰라요" }
}
```

3) 다시 물은 질문에 또 빈 답변이나 "몰라요"가 오면 더 묻지 않고 다음 order로 넘어감 (3번 질문이면 저장)
4) 다음 질문 요청의 `previousAnswers`에는 해당 order의 마지막 질문(다시 물은 질문)과 답변을 넣음

- 응답 형식은 기존과 같음 (`order`, `type`은 요청과 동일)
- `retry` 없이 보내면 기존과 똑같이 동작함
- 다시 묻기는 order마다 1번만, 횟수 관리는 백엔드가 함

#### 위험 내용 안전 모드

일기나 답변에 폭력, 학대, 괴롭힘, 따돌림, 자해, 성적 피해, 위협, 방임 같은 위험 내용이 있으면 안전 모드로 질문함

- 코드가 위험 낱말을 찾거나 LLM이 위험 내용으로 판단하면 안전 모드
- 아이의 말을 차분하게 받아들이고 비난하지 않음
- 폭력이나 괴롭힘을 아이의 잘못으로 돌리지 않음
- 잘잘못은 어느 쪽으로도 판단하지 않음 ("네 잘못이 아니야", "아빠가 잘못했어" 모두 쓰지 않고 "무서운 마음이 들 수 있어"처럼 감정만 인정함)
- 사건을 사실처럼 되풀이하지 않고 아이의 말을 의심하지도 않음 ("아빠가 때려서 무서웠구나" 대신 "그런 일이 있어서 무서웠구나")
- 사건의 세부 내용(어떻게, 몇 번, 언제부터, 왜)을 캐묻지 않음
- 관점 확장 대신 안전과 도움 요청을 묻고, 상대의 마음이나 이유를 묻는 질문은 막음 (예: "아빠는 왜 그랬을까?" 금지)
- 지금 위험하다면 가까운 안전한 어른에게 도움을 요청하도록 안내함
- 보호자가 상대일 수 있으므로 도움 요청 대상을 부모로만 정하지 않고 선생님 등 다른 어른도 함께 제시함
- 응답 형식은 기존과 같고, 안전 모드 여부는 응답에 따로 표시하지 않음

| 순서 | 안전 모드 질문 목적 |
| --- | --- |
| 1 (EMOTION) | 이야기해 준 것을 받아 주고 지금 마음을 물음 |
| 2 (REASON) | 이유를 묻지 않고, 아이가 고른 감정을 인정하며 필요한 도움을 물음 |
| 3 (PERSPECTIVE) | 어른에게 말해도 된다고 안내한 뒤 떠오르는 안전한 어른이 있는지 부담 없이 물음 |

기본 질문 (디자인 기본 문구와 맞추기로 함, 디자인 문구를 받으면 아래 문구를 교체할 예정)

| type | 기본 질문 (`{감정}`은 선택한 감정에 맞게 바뀜) |
| --- | --- |
| EMOTION | `{기뻤을 때}` 마음속에서 어떤 느낌이 들었니? |
| REASON | 어떤 일 때문에 `{기쁜 마음}`이 들었을까? |
| PERSPECTIVE | 친구가 같은 일을 겪었다면, 너는 친구에게 어떤 말을 해 주고 싶니? |

다시 묻기 기본 질문

| type | 기본 질문 |
| --- | --- |
| EMOTION | 그때 `{기쁜 마음}`이 아주 컸니, 아니면 조금이었니? |
| REASON | 그 일에서 어떤 순간이 가장 기억에 남니? |
| PERSPECTIVE | 다음에 비슷한 일이 생기면 어떻게 하고 싶니? |

안전 모드 기본 질문

| type | 기본 질문 |
| --- | --- |
| EMOTION | 솔직하게 이야기해 줘서 고마워, 지금은 마음이 어떠니? |
| REASON | `{무서운 마음}`이 들 수 있어, 지금 무엇이 있으면 마음이 조금 편해질까? |
| PERSPECTIVE | 무섭거나 위험할 때는 선생님이나 믿을 수 있는 어른에게 말해도 돼, 지금 떠오르는 어른이 있니? |
| 다시 묻기 (공통) | 말하기 어려우면 괜찮아, 지금 곁에서 너를 도와줄 수 있는 선생님이나 어른이 있니? |

### 감정 리포트

```json
// 200 OK
{ "most_emotion_reason": "...", "least_emotion_reason": "...", "parent_advice": "...", "trend_interpretation": "..." }
```

- `totalDiaryCount: 0`이면 LLM을 부르지 않고 명세서의 '일기 0건' 문구를 그대로 돌려줌
- 생성에 실패하면 `503` 응답, 백엔드는 기본 문구로 대체하고 실패 결과는 DB에 저장하지 않음
- 요청 통계가 서로 맞지 않으면 `422` 응답

### 공통 오류 형식

```json
{ "error": { "code": "INVALID_REQUEST", "message": "요청 형식 오류", "details": ["order 2의 type은 REASON이어야 합니다. (받은 값: PERSPECTIVE)"] } }
```

| 상태 | code | 의미 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | `AI_API_KEY`를 설정했는데 `X-API-Key` 헤더가 없거나 틀림 |
| 422 | `INVALID_REQUEST` | 요청 형식 오류 (백엔드 수정 필요) |
| 503 | `AI_GENERATION_FAILED` | 리포트 문구 생성 실패 (기본 문구 사용) |

### 타임아웃

- AI 서버는 요청 1건을 질문 약 12초, 리포트 약 25초 안에 끝냄 (재시도 포함)
- 백엔드 타임아웃은 리포트 30초로 합의함, 질문은 15초 정도 권장

## 부적절한 출력 막기

- LLM 결과를 그대로 보내지 않고 코드로 한 번 더 검사함
- 규칙을 어기면 이유를 알려 주고 1번 다시 생성함
- 그래도 안 되면 질문은 기본 질문, 리포트는 503으로 응답함

검사 규칙

- 질문
  - 물음표 하나로 끝나는 한 문장, 80자 이하
  - 영어, 감정 코드, 마크다운 금지
  - 진단, 비하 표현 금지 (단, 아이가 일기에 직접 쓴 낱말은 허용함)
  - 일기 속 구체적인 장면 낱말(예: 운동장, 공놀이)이 질문에 하나 이상 들어가야 함, 일기에 한국어 낱말이 없으면 이 검사는 건너뜀
- 리포트
  - 문장 수: 1~2문장, 조언은 1문장
  - 받은 통계에 없는 숫자 금지
  - 진단 표현이나 "좋아졌다, 나빠졌다" 같은 단정 금지
  - 기록되지 않은 감정을 "느끼지 않았다"고 단정하는 표현 금지

금지어 목록은 `app/question/validator.py`, `app/report/validator.py`에서 수정 가능

## 비용 참고

- 모델은 기본으로 `gpt-5.4-mini`를 쓰고 `.env`의 `OPENAI_MODEL`로 바꿀 수 있음
- 요청마다 사용한 토큰 수 확인 가능
- 아이의 일기가 OpenAI에 저장되지 않도록 `store=False`로 호출함
- 로그에는 일기 내용을 남기지 않음

## 백엔드와 합의한 내용

| 항목 | 결과 |
| --- | --- |
| 질문 응답의 `isFallback` | 백앤드는 AI가 보낸 값을 그대로 프론트에 전달 |
| 잘못된 요청 → 422 + `{"error": {"code", "message"}}` | 백엔드 확인 완료 |
| `previousAnswers` | 백엔드는 항상 order 순서대로, 빠짐없이 전달 |
| AI 서버 다운, 타임아웃 시 질문 | 백엔드 디자인 기반 자체 기본 문구 사용 |
| 리포트 응답 필드 | snake_case, 백엔드가 해당 키로 읽음 |
| 리포트 503, 타임아웃 | 백엔드가 기본 문구로 대체하고 통계와 함께 반환, 실패 결과는 DB에 저장하지 않음 |
| AI 기본 질문 문구 | 디자인 기본 문구와 맞추기로 함 |
| 백엔드 타임아웃 | 리포트 30초 |
| 질문 요청 `age`, 리포트 요청 `guardianType` | 추가하지 않음 |
| 위험 내용 감지 시 도움 안내 | 프론트에 보여 주지 않음 |

아직 정하지 않은 것

- `X-API-Key` 인증을 쓸지

## 추후 결정되면 수정할 것

- 디자인 기본 문구를 받으면 AI 기본 질문 문구 교체
- `trend_title` 생성 여부
- 응답에 위험 여부를 표시할지
- 배포 위치, 인증 방식, 백엔드와의 통신 방법
