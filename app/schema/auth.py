from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schema.user import UserOut


class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    # 8-72 chars, mixing letters and digits. The 72 ceiling is bcrypt's
    # effective byte limit -- it silently ignores anything past 72 bytes, so we
    # reject longer inputs rather than pretend the extra characters add security.
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value):
            raise ValueError("Password must contain at least one letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one number")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut