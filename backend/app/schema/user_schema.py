from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_ .-]+$")
    password: str = Field(min_length=10, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.lower()

    @field_validator("username")
    @classmethod
    def trim_username(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Username must contain at least 3 characters")
        return value

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode()) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False


class TokenResponse(BaseModel):
    message: str = "Login successful"


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_ .-]+$"
    )
    bio: str | None = Field(default=None, max_length=240)


class PublicUser(BaseModel):
    id: UUID
    username: str
    profile_picture_url: str | None = None
    bio: str = ""
    model_config = ConfigDict(from_attributes=True)


class UserResponse(PublicUser):
    email: EmailStr
    is_admin: bool = False
    created_at: datetime


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=10, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        return UserCreate.password_bytes(value)


class SensitiveAction(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
