from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Any


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


# Predefined errors
class EmailExistsError(AppError):
    def __init__(self):
        super().__init__("Email already registered", "EMAIL_EXISTS", 409)


class InvalidCredentialsError(AppError):
    def __init__(self):
        super().__init__("Invalid email or password", "INVALID_CREDENTIALS", 401)


class EmailNotVerifiedError(AppError):
    def __init__(self):
        super().__init__("Please verify your email before logging in", "EMAIL_NOT_VERIFIED", 403)


class TokenExpiredError(AppError):
    def __init__(self):
        super().__init__("Token has expired", "TOKEN_EXPIRED", 401)


class TokenInvalidError(AppError):
    def __init__(self):
        super().__init__("Token is invalid", "TOKEN_INVALID", 401)


class RateLimitExceededError(AppError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", 429)


class NotFoundError(AppError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", "NOT_FOUND", 404)


class ForbiddenError(AppError):
    def __init__(self):
        super().__init__("Access forbidden", "FORBIDDEN", 403)


def success_response(data: Any, message: str = "Success", status_code: int = 200) -> dict:
    return {"success": True, "message": message, "data": data}


def error_response(message: str, code: str, status_code: int) -> dict:
    return {"success": False, "message": message, "code": code, "statusCode": status_code}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.message, exc.code, exc.status_code),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    message = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    return JSONResponse(
        status_code=422,
        content=error_response(message, "VALIDATION_ERROR", 422),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {
        401: "TOKEN_INVALID",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(str(exc.detail), code, exc.status_code),
    )
