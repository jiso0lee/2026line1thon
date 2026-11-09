# OpenAI 호출 실패
class LLMError(Exception):
    pass

# LLM 결과가 생성 규칙을 어김
class InvalidOutputError(Exception):
    pass

# 재시도 후에도 리포트 문구 생성 실패, 503으로 응답
class ReportGenerationError(Exception):
    pass
