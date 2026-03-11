import pytest
from src.core.security import hash_password, verify_password, create_access_token, decode_access_token
from src.core.exceptions import TokenExpiredError, TokenInvalidError


def test_hash_and_verify_password():
    password = "MySecurePass123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword", hashed)


def test_create_and_decode_token():
    data = {"sub": "user-123", "email": "test@example.com", "name": "Test User"}
    token = create_access_token(data)
    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "test@example.com"


def test_decode_invalid_token():
    with pytest.raises(TokenInvalidError):
        decode_access_token("not.a.valid.token")
