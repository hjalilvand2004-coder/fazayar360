class AppError(Exception):
    """خطای ساختاریافته: پاسخ {error:{code,message,details}, request_id}."""

    def __init__(self, status: int, code: str, message: str, details: list | dict | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, details: list | None = None):
        super().__init__(409, code, message, details)


class NotFoundError(AppError):
    def __init__(self, message: str = "موردی یافت نشد"):
        super().__init__(404, "NOT_FOUND", message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "دسترسی مجاز نیست"):
        super().__init__(403, "FORBIDDEN", message)


class ValidationError(AppError):
    def __init__(self, message: str = "داده نامعتبر است", details: list | None = None):
        super().__init__(422, "VALIDATION_ERROR", message, details)
