from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config.settings import get_settings

settings = get_settings()

# This app uses synchronous SQLAlchemy (plain create_engine + Session)
# throughout every repository -- an async driver in DATABASE_URL (e.g.
# postgresql+asyncpg://...) will connect but then fail with a cryptic
# "MissingGreenlet" error the moment a query actually runs. Fail loudly
# and immediately instead, with a fix in the message.
if "+asyncpg" in settings.DATABASE_URL or "+aiosqlite" in settings.DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL uses an async driver (e.g. '+asyncpg'), but this app's "
        "database layer is synchronous. Remove the '+asyncpg' part so the URL "
        "starts with 'postgresql://' (uses psycopg2, already in requirements.txt) "
        "instead of 'postgresql+asyncpg://'."
    )

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()