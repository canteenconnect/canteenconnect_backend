class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "service_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code