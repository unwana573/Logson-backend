import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config.settings import get_settings
from app.config.database import Base, engine
from app.config.ratelimit import limiter
from app.router import auth, categories, feedback, orders, products, users

logger = logging.getLogger(__name__)
settings = get_settings()

# For a real deployment, replace this with Alembic migrations (you already
# use that pattern in your other FastAPI projects). create_all() is fine for
# local development and demos.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Logson API", version="1.0.0")

# Wire the slowapi rate limiter: the per-route @limiter.limit decorators read
# the limiter off app.state, and RateLimitExceeded is rendered as HTTP 429.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allowing credentials together with a wildcard origin is invalid per the
# CORS spec and unsafe -- it would let any site make authenticated calls. So
# only enable credentials when the origins are explicitly pinned. Bearer-token
# auth (this app's model) works either way: the token rides in the
# Authorization header, which doesn't depend on allow_credentials.
_allow_all_origins = "*" in settings.CORS_ORIGINS
if _allow_all_origins:
    logger.warning(
        "CORS_ORIGINS is '*': credentials are disabled and every origin is "
        "allowed. Set CORS_ORIGINS to your frontend's real URL in production."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=not _allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(feedback.router)


@app.get("/health")
def health():
    return {"status": "ok"}