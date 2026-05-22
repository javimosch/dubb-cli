EXIT_SUCCESS = 0
EXIT_INVALID_ARGUMENT = 85
EXIT_RESOURCE_NOT_FOUND = 92
EXIT_RESOURCE_EXISTS = 93
EXIT_INTERNAL_ERROR = 110


class DubbError(Exception):
    def __init__(self, message, code=EXIT_INTERNAL_ERROR, details=None):
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self):
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class InvalidArgument(DubbError):
    def __init__(self, message, details=None):
        super().__init__(message, EXIT_INVALID_ARGUMENT, details)


class NotFound(DubbError):
    def __init__(self, resource, name):
        super().__init__(
            f"{resource} not found: {name}",
            EXIT_RESOURCE_NOT_FOUND,
            {"resource": resource, "name": name}
        )
