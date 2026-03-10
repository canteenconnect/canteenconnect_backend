class APIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error: str = "bad_request",
        details=None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error = error
        self.details = details

    def to_dict(self):
        payload = {
            "error": self.error,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload

