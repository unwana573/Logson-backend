from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repository.user_repository import UserRepository
from app.schema.auth import GoogleAuthRequest, LoginRequest, RefreshRequest, SignupRequest, TokenResponse
from app.schema.user import UserOut
from app.config.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.service.google_oauth import verify_google_id_token


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def _issue_tokens(self, user) -> TokenResponse:
        """Every path that ends in an authenticated session -- signup,
        login, Google sign-in, and refresh itself -- goes through this one
        place so access and refresh tokens are always issued as a pair."""
        access_token = create_access_token({"sub": user.id})
        refresh_token = create_refresh_token({"sub": user.id})
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserOut.model_validate(user),
        )

    def signup(self, payload: SignupRequest) -> TokenResponse:
        if self.users.get_by_email(payload.email):
            raise HTTPException(status_code=400, detail="An account with this email already exists")

        # The single rule that decides who runs the store: the very first
        # account ever created becomes admin. Every signup after that is a
        # normal user, full stop -- promotion after this point only happens
        # through UserService.set_role(), which requires an admin caller.
        # Google sign-in shares this same rule -- see google_auth() below.
        is_first_user = self.users.count() == 0

        user = self.users.create(
            full_name=payload.full_name,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            is_admin=is_first_user,
        )
        return self._issue_tokens(user)

    def login(self, payload: LoginRequest) -> TokenResponse:
        user = self.users.get_by_email(payload.email)
        if not user or not user.hashed_password:
            # Either no account, or the account was created via Google and
            # has never set a password -- same error either way, so we
            # don't leak which emails exist.
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        if not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="This account has been deactivated")

        return self._issue_tokens(user)

    def google_auth(self, payload: GoogleAuthRequest) -> TokenResponse:
        """Signs in an existing Google-linked user, links Google to an
        existing email/password account on first use, or creates a brand
        new account -- all through the one entry point the router calls."""
        profile = verify_google_id_token(payload.id_token)

        user = self.users.get_by_google_id(profile.google_id)

        if not user:
            existing_by_email = self.users.get_by_email(profile.email)
            if existing_by_email:
                # Same email already has a password account -- link Google
                # to it rather than creating a duplicate user.
                user = self.users.attach_google_id(existing_by_email, profile.google_id)
            else:
                # Brand new account. Same first-signup-is-admin rule as the
                # email/password path applies here too.
                is_first_user = self.users.count() == 0
                user = self.users.create_google_user(
                    full_name=profile.full_name,
                    email=profile.email,
                    google_id=profile.google_id,
                    is_admin=is_first_user,
                )

        if not user.is_active:
            raise HTTPException(status_code=403, detail="This account has been deactivated")

        return self._issue_tokens(user)

    def refresh(self, payload: RefreshRequest) -> TokenResponse:
        """Exchanges a still-valid refresh token for a brand new
        access/refresh pair, so the person doesn't have to log in again
        every time their short-lived access token expires."""
        token_payload = decode_refresh_token(payload.refresh_token)
        if token_payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        user_id = token_payload.get("sub")
        user = self.users.get_by_id(user_id) if user_id else None
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="This account has been deactivated")

        return self._issue_tokens(user)