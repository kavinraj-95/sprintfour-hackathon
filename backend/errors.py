"""The one error type the app raises, and the codes it uses.

Lives in its own module (not app.py) so any service can raise it without
importing the FastAPI app — that keeps the dependency arrow pointing one way:
routes/services -> errors, never the reverse.
"""
from __future__ import annotations


class AppError(Exception):
    """A domain error carrying an HTTP status, a stable code, and a message.

    Services raise this instead of letting an exception bubble into a bare 500.
    `app.py` registers a handler that renders it as an `ErrorResponse`.
    """

    def __init__(self, status_code: int, error: str, detail: str | None = None):
        self.status_code = status_code
        self.error = error
        self.detail = detail
        super().__init__(f"{error}: {detail}" if detail else error)
