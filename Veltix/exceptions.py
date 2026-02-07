class VeltixError(Exception):
    """
    Base exception class for all Veltix framework errors.
    """
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class MessageTypeError(VeltixError):
    """
    Exception raised for invalid message type operations.
    """
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class SenderError(VeltixError):
    """
    Exception raised for sender-related errors.
    """
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class RequestError(VeltixError):
    """
    Exception raised for request parsing or compilation errors.
    """
    def __init__(self, *args: object) -> None:
        super().__init__(*args)