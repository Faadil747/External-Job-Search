from fastapi import HTTPException, status


class AIUnavailableError(HTTPException):
    """Raise when an LLM/embedding call fails after retries. Callers in the API
    layer catch app.ai.llm_provider.LLMError and re-raise this so the frontend
    gets a clean 503 instead of a stack trace, per spec section 89: AI failures
    must never crash the app or block access to already-saved data."""

    def __init__(self, detail: str = "AI analysis is temporarily unavailable. Your saved profile and jobs remain accessible.") -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class DuplicateResourceError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class NotFoundError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
