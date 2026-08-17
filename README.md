# Logson backend

FastAPI + SQLAlchemy backend for the Logson software-license marketplace,
structured as layered: **router → service → repository**.

## Structure

```
app/
  config/        settings.py -- every env var read in one place
  schema/        Pydantic request/response models, one file per resource
  repository/    raw SQLAlchemy queries only, one class per model
  service/       business logic (first-signup-is-admin, checkout, stock
                 assignment, Paystack calls) -- calls repositories, never
                 touches the DB directly
  router/        thin FastAPI route functions -- parse the request, call
                 a service, return the result. No business logic here.
  models.py      SQLAlchemy ORM models
  database.py    engine/session setup
  security.py    password hashing + JWT
  deps.py        get_current_user / get_current_admin dependencies
  main.py        app factory, wires routers together
test/
  conftest.py    pytest fixtures: isolated in-memory DB + TestClient per test
  test_*.py      one file per resource, 31 tests total
```

Request flow for anything that touches the DB: **router** receives the
HTTP request → calls a **service** method → service calls one or more
**repository** methods → repository runs the SQLAlchemy query. Routers
never import `models` directly for queries, and services never build raw
SQLAlchemy queries themselves.

## Run locally

```bash
cp .env.example .env   # then fill in real values, especially LOGSON_SECRET_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000/docs for interactive API docs.

## Run tests

```bash
pytest -v
```

31 tests covering: first-signup-becomes-admin, only-admin-can-promote,
functional search, bulk stock-textarea parsing, manual-transfer approval
flow, stock/amount-spent crediting, and access control on every admin route.
Each test gets a fresh in-memory SQLite database, so there's no shared state
between tests and no `logson.db` file left behind.

## Environment variables

All read through `app/config/settings.py`:

- `DATABASE_URL` — defaults to local SQLite (`sqlite:///./logson.db`). Point this at Postgres in production, e.g. `postgresql://user:pass@host/db`.
- `LOGSON_SECRET_KEY` — JWT signing secret. Set a real random value in production.
- `GOOGLE_CLIENT_ID` — OAuth client ID from Google Cloud Console, required for `POST /auth/google`. Must match the client ID the frontend uses to request ID tokens.
- `PAYSTACK_SECRET_KEY` — your Paystack secret key, required for the `/orders/{id}/paystack/init` and `/paystack/verify` endpoints.
- `CORS_ORIGINS` — comma-separated list of allowed origins. Defaults to `*`; lock this down to your frontend's real URL in production.

## Business rules enforced server-side

- **First signup becomes admin.** `AuthService.signup()` checks if the users table is empty via `UserRepository.count()`; if so the new account is created with `is_admin=True`. Every signup after that defaults to `is_admin=False`. The same rule applies to the *first* Google sign-in — see `AuthService.google_auth()`.
- **Google sign-in.** `POST /auth/google` takes the ID token Google's Identity Services SDK hands the frontend and verifies it server-side (`app/service/google_oauth.py`) — the frontend never asserts who the user is, only Google's signed token does. If the Google account's email matches an existing password account, Google is linked to it rather than creating a duplicate user.
- **Only an admin can grant admin access.** `PATCH /users/{id}/role` sits behind the `get_current_admin` dependency (`app/deps.py`), which checks the *authenticated* user's `is_admin` flag from the database — not anything the client sends. A non-admin token gets a 403 regardless of what the request body says. `UserService.set_role()` adds one more guardrail on top: an admin can't strip their own admin access.
- **Search** — `GET /products?search=windows` matches product name or vendor, case-insensitively, via `ProductRepository.list_filtered()`.
- **No wallet/top-up system.** Users pay per order via `manual` (bank transfer + proof upload, admin approves) or `paystack` (init → redirect → verify). `User.amount_spent_kobo` accumulates only when `OrderService._assign_stock_and_credit()` runs, i.e. only on a confirmed paid order.

## Key endpoints

| Method | Path | Access |
|---|---|---|
| POST | /auth/signup | public |
| POST | /auth/login | public |
| POST | /auth/google | public |
| GET  | /auth/me | authenticated |
| GET  | /products?search=&category_id= | public |
| POST | /products | admin |
| POST | /products/{id}/stock | admin |
| GET  | /categories | public |
| POST | /categories | admin |
| GET  | /users | admin |
| PATCH | /users/{id}/role | admin |
| PATCH | /users/{id}/status | admin |
| GET  | /users/me/credentials | authenticated |
| POST | /orders | authenticated |
| GET  | /orders/me | authenticated |
| GET  | /orders?status= | admin |
| POST | /orders/{id}/approve | admin (manual transfer) |
| POST | /orders/{id}/reject | admin |
| POST | /orders/{id}/paystack/init | authenticated |
| POST | /orders/{id}/paystack/verify | authenticated |


1. The create product page should contain category( the admin would select from already created categories), name, description, price, stock, product image and when this is saved it should take the admin to part where  credentials would be added
2. the price shouldn`t be fixed on kobo it should be flexible based on how many figures are inputed
3. test that admin should be able to create, update and delete category
4. add google auth btn to the frontend
5. Users should be able through the landing page from a product button on the navbar
6. Thats the hosted backend url https://logson-backend.onrender.com replace local host with this and integrate it