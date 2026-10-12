"""Application errors mapped to consistent HTTP responses."""


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "error",
        details: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or []


class SpecError(AppError):
    def __init__(self, message: str, details: list[dict[str, str]] | None = None) -> None:
        super().__init__(
            message,
            status_code=400,
            code="validation_error",
            details=details,
        )


class InvariantError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500, code="invariant_violation")


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status_code=404, code="not_found")


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409, code="conflict")


class LimitError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400, code="limit_exceeded")


class PayloadTooLarge(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=413, code="payload_too_large")


class Cancelled(Exception):
    """Cooperative cancellation of a simulation run."""


class ProviderError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
