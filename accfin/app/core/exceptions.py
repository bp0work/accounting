from fastapi import HTTPException, status


class AppHTTPException(HTTPException):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(
            status_code=status_code,
            detail={"error": {"code": code, "message": message}},
        )


def unauthorized(code: str, message: str) -> AppHTTPException:
    return AppHTTPException(status.HTTP_401_UNAUTHORIZED, code, message)


def forbidden(code: str, message: str) -> AppHTTPException:
    return AppHTTPException(status.HTTP_403_FORBIDDEN, code, message)


def rate_limited(message: str = "Too many login attempts; retry after 60s") -> AppHTTPException:
    return AppHTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED", message)
