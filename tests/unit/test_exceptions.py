import pytest
from src.core.exceptions import (
    AppError,
    EmailExistsError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    TokenExpiredError,
    TokenInvalidError,
    RateLimitExceededError,
    NotFoundError,
    ForbiddenError,
    success_response,
    error_response,
)


# ── AppError base class ──────────────────────────────────────────────────────

def test_app_error_basic():
    err = AppError("something broke", "SOMETHING_BROKE", 400)
    assert err.message == "something broke"
    assert err.code == "SOMETHING_BROKE"
    assert err.status_code == 400
    assert str(err) == "something broke"


def test_app_error_default_status_code():
    err = AppError("oops", "OOPS")
    assert err.status_code == 400


def test_app_error_is_exception():
    err = AppError("test", "TEST", 500)
    assert isinstance(err, Exception)


# ── Predefined error classes ──────────────────────────────────────────────────

def test_email_exists_error():
    err = EmailExistsError()
    assert err.code == "EMAIL_EXISTS"
    assert err.status_code == 409
    assert "already registered" in err.message.lower() or "email" in err.message.lower()


def test_invalid_credentials_error():
    err = InvalidCredentialsError()
    assert err.code == "INVALID_CREDENTIALS"
    assert err.status_code == 401


def test_email_not_verified_error():
    err = EmailNotVerifiedError()
    assert err.code == "EMAIL_NOT_VERIFIED"
    assert err.status_code == 403


def test_token_expired_error():
    err = TokenExpiredError()
    assert err.code == "TOKEN_EXPIRED"
    assert err.status_code == 401


def test_token_invalid_error():
    err = TokenInvalidError()
    assert err.code == "TOKEN_INVALID"
    assert err.status_code == 401


def test_rate_limit_exceeded_error_default():
    err = RateLimitExceededError()
    assert err.code == "RATE_LIMIT_EXCEEDED"
    assert err.status_code == 429
    assert "rate limit" in err.message.lower()


def test_rate_limit_exceeded_error_custom_message():
    err = RateLimitExceededError("Too many uploads")
    assert err.code == "RATE_LIMIT_EXCEEDED"
    assert err.message == "Too many uploads"


def test_not_found_error_default():
    err = NotFoundError()
    assert err.code == "NOT_FOUND"
    assert err.status_code == 404
    assert "not found" in err.message.lower()


def test_not_found_error_custom_resource():
    err = NotFoundError("Analysis")
    assert err.code == "NOT_FOUND"
    assert "Analysis" in err.message


def test_forbidden_error():
    err = ForbiddenError()
    assert err.code == "FORBIDDEN"
    assert err.status_code == 403


# ── All predefined errors are AppError subclasses ────────────────────────────

@pytest.mark.parametrize("exc_class", [
    EmailExistsError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    TokenExpiredError,
    TokenInvalidError,
    ForbiddenError,
])
def test_predefined_errors_are_app_errors(exc_class):
    err = exc_class()
    assert isinstance(err, AppError)


def test_not_found_is_app_error():
    assert isinstance(NotFoundError("X"), AppError)


def test_rate_limit_is_app_error():
    assert isinstance(RateLimitExceededError(), AppError)


# ── success_response helper ──────────────────────────────────────────────────

def test_success_response_basic():
    result = success_response({"key": "value"})
    assert result["success"] is True
    assert result["data"] == {"key": "value"}
    assert result["message"] == "Success"


def test_success_response_custom_message():
    result = success_response(None, "Created", 201)
    assert result["success"] is True
    assert result["message"] == "Created"
    assert result["data"] is None


def test_success_response_with_list():
    result = success_response([1, 2, 3], "Items retrieved")
    assert result["success"] is True
    assert result["data"] == [1, 2, 3]


# ── error_response helper ────────────────────────────────────────────────────

def test_error_response_basic():
    result = error_response("Something went wrong", "INTERNAL_ERROR", 500)
    assert result["success"] is False
    assert result["message"] == "Something went wrong"
    assert result["code"] == "INTERNAL_ERROR"
    assert result["statusCode"] == 500


def test_error_response_fields():
    result = error_response("Not found", "NOT_FOUND", 404)
    assert "success" in result
    assert "message" in result
    assert "code" in result
    assert "statusCode" in result
