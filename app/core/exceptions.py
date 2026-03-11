"""
Core exceptions module.

Minimal custom exception types for application-level error handling.
"""


class AppException(Exception):
    """Base exception for application-level errors."""

    def __init__(self, message: str = "An unexpected error occurred.") -> None:
        super().__init__(message)
        self.message = message


class DatabaseConnectionException(AppException):
    """Raised when the application cannot connect to the database."""

    def __init__(self, message: str = "Database connection failed.") -> None:
        super().__init__(message)
