from pydantic import BaseModel, EmailStr, ConfigDict
import uuid
from datetime import datetime


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    image: str | None = None


class AuthResponse(BaseModel):
    accessToken: str
    user: UserPublic
