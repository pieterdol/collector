"""Small helpers shared by API tests."""


def auth_headers(client, email="user@example.com", name="User") -> dict[str, str]:
    """Register a fresh user and return Authorization headers for them."""
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "test-password-1", "display_name": name},
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def create_item(client, headers, **overrides) -> dict:
    payload = {
        "type": "book",
        "format": "physical",
        "status": "backlog",
        "title": "Dune",
        "metadata": {"authors": ["Frank Herbert"]},
    }
    payload.update(overrides)
    res = client.post("/api/items", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()
