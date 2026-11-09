# 생각의힘 AI 서버

BE1·BE2가 호출하는 AI 서버예요. DB 없이 요청을 받아 결과만 돌려줘요.

| API | 호출 | 하는 일 |
| --- | --- | --- |
| `POST /api/diary-questions/generate` | BE1 → AI | 일기 + 이전 답변을 보고 질문 1개 생성 |
| `POST /api/emotion-reports/generate` | BE2 → AI | 기간 통계를 보고 설명 문구 4개 생성 |
| `GET /health` | 배포 환경 | 상태 확인 (인증 없음) |
| `GET /docs` | 사람 | Swagger 문서. 여기서 직접 요청을 보내 볼 수 있어요 |

## 폴더 구조

```
app/
  main.py            FastAPI 앱, 라우트, 오류 응답 형식
  config.py          환경변수 설정
  domain.py          감정 코드·질문 유형·순서 (명세서 고정값)
  schemas.py         요청/응답 JSON 형식 + 요청 검증(order/type 짝 등)
  llm.py             OpenAI 호출 (Responses API + Structured Outputs)
  question/          질문 생성: 프롬프트 · '몰라요' 판별 · 출력 검증 · 기본 질문
  report/            리포트: 최다/최소 정리 · 프롬프트 · 출력 검증
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
cp .env.example .env      # OPENAI_API_KEY 채우기

# 4) 실행 → http://localhost:8000/docs
uvicorn app.main:app --reload --env-file .env
```

테스트: `pytest -q`
실제 질문 품질 확인: `python -m scripts.try_live` (리포트는 `--report`)

## Docker

```bash
docker build -t saenggak-ai .
docker run --rm --env-file .env -p 8000:8000 saenggak-ai
```

M 시리즈 Mac에서 만든 이미지를 x86 서버에 올릴 때는
`docker build --platform linux/amd64 -t saenggak-ai .` 로 빌드하세요.

## BE가 알아야 할 응답 규칙

### 질문 생성

```json
// 200 OK
{ "order": 2, "type": "REASON", "content": "친구가 공을 넘겨줬을 때 왜 고마운 마음이 들었니?", "isFallback": false }
```

- `isFallback: true`면 AI가 질문을 만들지 못해 **기본 질문**을 돌려준 것이에요. 이때도 200이에요.
- 요청이 명세와 다르면 `422`예요. 예를 들어 order와 type 짝이 틀리거나, previousAnswers 개수나 순서가 틀리거나, 감정 코드가 틀린 경우예요.
- 답변이 비어 있거나 "몰라요"처럼 정보가 없으면, 그 답변은 근거로 쓰지 않고 일기 본문을 바탕으로 질문해요.

기본 질문 (BE1이 AI 서버에 연결하지 못할 때도 같은 문구를 쓰면 좋아요):

| type | 기본 질문 (`{감정}`은 선택한 감정에 맞게 바뀜) |
| --- | --- |
| EMOTION | `{기뻤을 때}` 마음속에서 어떤 느낌이 들었니? |
| REASON | 어떤 일 때문에 `{기쁜 마음}`이 들었을까? |
| PERSPECTIVE | 친구가 같은 일을 겪었다면, 너는 친구에게 어떤 말을 해 주고 싶니? |

### 감정 리포트

```json
// 200 OK (명세서대로 snake_case)
{ "most_emotion_reason": "...", "least_emotion_reason": "...", "parent_advice": "...", "trend_interpretation": "..." }
```

- `totalDiaryCount: 0`이면 LLM을 부르지 않고 명세서의 '일기 0건' 문구를 그대로 돌려줘요.
- 생성에 실패하면 `503`이에요. 이때 BE2는 명세서의 기본 문구를 쓰고, **그 결과를 리포트로 저장(캐시)하지 않아야** 해요.
- 요청 통계가 서로 맞지 않으면 `422`예요. 예를 들어 감정 6종이 다 없거나, count 합계와 totalDiaryCount가 다르거나, days가 기간 밖이거나 날짜순이 아닌 경우예요.

### 공통 오류 형식

```json
{ "error": { "code": "INVALID_REQUEST", "message": "요청 형식이 명세서와 다릅니다.", "details": ["order 2의 type은 REASON이어야 합니다. (받은 값: PERSPECTIVE)"] } }
```

| 상태 | code | 의미 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | `AI_API_KEY`를 설정했는데 `X-API-Key` 헤더가 없거나 틀림 |
| 422 | `INVALID_REQUEST` | 요청 형식 오류 (BE 쪽 수정 필요) |
| 503 | `AI_GENERATION_FAILED` | 리포트 문구 생성 실패 (기본 문구 사용) |

### 타임아웃

AI 서버는 요청 1건을 질문 약 12초, 리포트 약 25초 안에 끝내요(재시도 포함). BE 쪽 타임아웃은 질문 15초, 리포트 30초 정도로 잡아 주세요.

## 부적절한 출력 막기

LLM 결과를 그대로 보내지 않고 코드로 한 번 더 검사해요. 어기면 이유를 알려 주고 1번 다시 생성하고, 그래도 안 되면 질문은 기본 질문, 리포트는 503으로 응답해요.

- **질문**
  - 물음표 하나로 끝나는 한 문장, 80자 이하
  - 영어·감정 코드·마크다운 금지
  - 진단·비하 표현 금지. 단, 아이가 일기에 직접 쓴 낱말은 허용해요.
  - 일기 속 구체적인 장면 낱말(예: 운동장, 공놀이)이 질문에 하나 이상 들어가야 해요. 일기에 한국어 낱말이 없으면 이 검사는 건너뛰어요.
- **리포트**
  - 문장 수: 1~2문장, 조언은 1문장
  - 받은 통계에 없는 숫자 금지. 예를 들어 반올림한 "약 67%"도 걸러요.
  - 진단 표현이나 "좋아졌다·나빠졌다" 같은 단정 금지
  - 기록되지 않은 감정을 "느끼지 않았다"고 단정하는 표현 금지

금지어 목록은 `app/question/validator.py`, `app/report/validator.py`에서 바로 고칠 수 있어요.

## 비용 참고

모델은 기본으로 `gpt-5.4-mini`를 써요. `.env`의 `OPENAI_MODEL`로 바꿀 수 있어요. 요청마다 사용한 토큰 수가 로그(`openai call ... input_tokens=... output_tokens=...`)에 남아요. 시연 전에 `try_live`로 몇 번 돌려 보고 실제 사용량을 확인하세요.

아이의 일기가 OpenAI에 저장되지 않도록 `store=False`로 호출해요. 로그에는 일기 내용을 남기지 않아요.

## BE와 합의한 내용

| 항목 | 결과 |
| --- | --- |
| 질문 응답의 `isFallback` | BE1이 AI가 보낸 값을 그대로 프론트에 전달 |
| 잘못된 요청 → 422 + `{"error": {"code", "message"}}` | BE1 확인 완료 |
| `previousAnswers` | BE1이 항상 order 순서대로, 빠짐없이 전달 |
| AI 서버 다운·타임아웃 시 질문 | BE1이 디자인 기반 자체 기본 문구 사용 |
| 리포트 응답 필드 | 명세서대로 snake_case. BE2가 해당 키로 읽음 |
| 리포트 503·타임아웃 | BE2가 기본 문구로 대체하고 통계와 함께 반환. 실패 결과는 DB에 저장하지 않음 |

아직 정하지 않은 것:
- AI 기본 질문 문구를 디자인 기본 문구와 맞출지
- BE 쪽 타임아웃 값 (권장: 질문 15초, 리포트 30초)
- 선택 기능인 `X-API-Key` 인증을 쓸지

## 추후 결정되면 수정할 것

- 질문 요청에 `age`, 리포트 요청에 `guardianType` 추가
- `trend_title` 생성 여부
- 위험한 내용(따돌림·학대·자해 암시 등) 감지 시 처리
- 배포 위치, 인증 방식, BE와의 통신 방법
