"""Structured application errors with error codes."""


class AppError(Exception):
    """Application error with machine-readable code and HTTP status."""

    def __init__(self, code: str, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.status_code = status_code
        self.detail = detail


# Error code constants
FILE_NOT_FOUND = "FILE_NOT_FOUND"
FILE_READ_ONLY = "FILE_READ_ONLY"
FILE_LOCKED = "FILE_LOCKED"
FILE_CHANGED = "FILE_CHANGED"
DISK_FULL = "DISK_FULL"
INVALID_WAV = "INVALID_WAV"
VALIDATION_ERROR = "VALIDATION_ERROR"
MODEL_NOT_READY = "MODEL_NOT_READY"
ANALYSIS_FAILED = "ANALYSIS_FAILED"
RENAME_CONFLICT = "RENAME_CONFLICT"
