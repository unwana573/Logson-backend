import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    """A fresh in-memory SQLite database per test, so tests never leak
    state into each other (important for the 'first signup is admin'
    rule, which depends on the users table being empty).

    StaticPool is required here: without it, SQLite hands each new
    connection its own throwaway :memory: database, so the tables created
    below would be invisible to the connection FastAPI opens per request."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_token(client):
    """Signs up the first user (auto-admin) and returns their bearer token."""
    res = client.post(
        "/auth/signup",
        json={"full_name": "Admin User", "email": "admin@logson.ng", "password": "password123"},
    )
    return res.json()["access_token"]


@pytest.fixture()
def user_token(client, admin_token):
    """Signs up a second user (regular, non-admin) and returns their token.
    Depends on admin_token so the admin always exists first."""
    res = client.post(
        "/auth/signup",
        json={"full_name": "Regular User", "email": "user@logson.ng", "password": "password123"},
    )
    return res.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
