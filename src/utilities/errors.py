class NotFoundError(LookupError):
    """The job doesn't exist (or already expired)."""


class QuotaExceededError(RuntimeError):
    """The caller used up its daily job quota."""
