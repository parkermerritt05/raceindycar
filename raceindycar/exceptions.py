class FastIndyCarError(Exception):
    """Base exception for fastindycar."""


class RateLimitExceededError(FastIndyCarError):
    """Raised when the IndyCar site's request rate limit is exceeded."""
