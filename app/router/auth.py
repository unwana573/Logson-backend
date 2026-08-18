from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app import models
from app.config.database import get_db
from app.config.deps import get_current_user
from app.config.ratelimit import limiter
from app.schema.auth import GoogleAuthRequest, LoginRequest, RefreshRequest, SignupRequest, TokenResponse
from app.schema.user import UserOut
from app.service.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


# Rate limits are keyed per client IP (see app/config/ratelimit.py). They exist
# to blunt brute-force / credential-stuffing and signup spam -- generous enough
# not to bother a real person, tight enough to stop a script. slowapi requires
# the decorated route to accept a parameter named `request`.
@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def signup(request: Request, payload: SignupRequest, db: Session = Depends(get_db)):
    return AuthService(db).signup(payload)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    return AuthService(db).login(payload)


@router.post("/google", response_model=TokenResponse)
@limiter.limit("10/minute")
def google_auth(request: Request, payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Frontend sends the ID token from Google Identity Services here.
    Verified server-side in AuthService.google_auth -- the frontend never
    tells us who the user is, only Google's signed token does."""
    return AuthService(db).google_auth(payload)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """Frontend calls this with the refresh token once the access token
    (short-lived, ACCESS_TOKEN_EXPIRE_MINUTES) has expired, to get a new
    pair without asking the person to log in again."""
    return AuthService(db).refresh(payload)


@router.get("/me", response_model=UserOut)
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user
