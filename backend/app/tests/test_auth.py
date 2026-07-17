def register(client, email="pieter@example.com", password="hunter2!", name="Pieter"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )


def test_register_returns_token_and_user(client):
    res = register(client)
    assert res.status_code == 201
    body = res.json()
    assert body["token"]
    assert body["user"]["email"] == "pieter@example.com"
    assert body["user"]["display_name"] == "Pieter"
    assert "password" not in str(body)


def test_register_duplicate_email_conflicts(client):
    register(client)
    res = register(client)
    assert res.status_code == 409


def test_email_is_case_insensitive(client):
    register(client, email="Pieter@Example.com")
    res = register(client, email="pieter@example.COM")
    assert res.status_code == 409
    res = client.post(
        "/api/auth/login", json={"email": "PIETER@example.com", "password": "hunter2!"}
    )
    assert res.status_code == 200


def test_login_with_wrong_password_fails(client):
    register(client)
    res = client.post(
        "/api/auth/login", json={"email": "pieter@example.com", "password": "wrong"}
    )
    assert res.status_code == 401


def test_login_unknown_email_fails(client):
    res = client.post("/api/auth/login", json={"email": "who@where.com", "password": "x"})
    assert res.status_code == 401


def test_me_returns_current_user(client):
    token = register(client).json()["token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "pieter@example.com"


def test_me_rejects_missing_or_garbage_token(client):
    assert client.get("/api/auth/me").status_code == 401
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"})
    assert res.status_code == 401


def test_password_is_stored_hashed(client):
    register(client)
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user = db.scalars(select(User)).one()
        assert user.password_hash != "hunter2!"
        assert user.password_hash.startswith("$argon2")
