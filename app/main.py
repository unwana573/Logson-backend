from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.database import Base, engine
from app.router import auth, categories, orders, products, users

settings = get_settings()

# For a real deployment, replace this with Alembic migrations (you already
# use that pattern in your other FastAPI projects). create_all() is fine for
# local development and demos.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Logson API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(orders.router)


@app.get("/health")
def health():
    return {"status": "ok"}
