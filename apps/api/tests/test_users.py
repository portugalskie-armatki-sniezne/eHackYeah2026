from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import create_user, login, user_payload


def test_create_user_returns_user_without_password(client: TestClient, connection: psycopg.Connection):
    user = create_user(client, first_name="  Anna  ")

    assert user["first_name"] == "Anna"
    assert user["role"] == "user"
    assert "password" not in user and "password_hash" not in user
    stored = connection.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],)).fetchone()
    assert stored["password_hash"].startswith("$argon2")


def test_create_user_rejects_role_and_invalid_data(client: TestClient):
    assert client.post("/users", json=user_payload(role="admin")).status_code == 422
    assert client.post("/users", json=user_payload(email="not-an-email")).status_code == 422
    assert client.post("/users", json=user_payload(first_name="   ")).status_code == 422
    assert client.post("/users", json=user_payload(password="short")).status_code == 422


def test_create_user_with_taken_email_conflicts(client: TestClient):
    user = create_user(client)

    response = client.post("/users", json=user_payload(email=user["email"]))

    assert response.status_code == 409


@pytest.mark.parametrize("role", ["user", "office"])
def test_only_admin_can_list_users(client: TestClient, signed_in, role: str):
    _, headers = signed_in(role)

    assert client.get("/users").status_code == 401
    assert client.get("/users", headers=headers).status_code == 403


def test_admin_lists_users_with_pagination(client: TestClient, signed_in):
    admin, headers = signed_in("admin")
    total = client.get("/users", headers=headers).json()["total"]
    created = [create_user(client) for _ in range(3)]

    page = client.get("/users", params={"limit": 2, "offset": total + 1}, headers=headers).json()
    # created_at is the same within the test transaction, so only membership is stable.
    new_users = client.get("/users", params={"limit": 200, "offset": total - 1}, headers=headers).json()["items"]

    assert page["total"] == total + 3
    assert page["limit"] == 2 and page["offset"] == total + 1
    assert len(page["items"]) == 2
    assert {user["id"] for user in new_users} == {user["id"] for user in [admin, *created]}
    assert client.get("/users", params={"limit": 201}, headers=headers).status_code == 422


@pytest.mark.parametrize("role", ["user", "office"])
def test_non_admin_accesses_only_own_account(client: TestClient, signed_in, role: str):
    user, headers = signed_in(role)
    other = create_user(client)

    assert client.get(f"/users/{user['id']}", headers=headers).json() == user
    for missing_or_other in (other["id"], uuid4()):
        url = f"/users/{missing_or_other}"
        assert client.get(url, headers=headers).status_code == 403
        assert client.patch(url, json={"first_name": "Jan"}, headers=headers).status_code == 403
        assert client.delete(url, headers=headers).status_code == 403
    assert client.get(f"/users/{user['id']}").status_code == 401


def test_admin_accesses_any_account(client: TestClient, signed_in):
    _, headers = signed_in("admin")
    other = create_user(client)

    assert client.get(f"/users/{other['id']}", headers=headers).json() == other
    assert client.get(f"/users/{uuid4()}", headers=headers).status_code == 404
    response = client.patch(f"/users/{other['id']}", json={"first_name": "Jan"}, headers=headers)
    assert response.json()["first_name"] == "Jan"
    assert client.delete(f"/users/{other['id']}", headers=headers).status_code == 204


def test_update_own_account(client: TestClient, signed_in, connection: psycopg.Connection):
    user, headers = signed_in("user")

    response = client.patch(f"/users/{user['id']}", headers=headers,
                            json={"last_name": "Kowalska", "phone": None, "password": "nowe-haslo"})

    assert response.status_code == 200
    assert response.json() == user | {"last_name": "Kowalska", "phone": None}
    login(client, user["email"], "nowe-haslo")


def test_update_rejects_invalid_changes(client: TestClient, signed_in):
    user, headers = signed_in("user")
    other = create_user(client)
    url = f"/users/{user['id']}"

    assert client.patch(url, json={"first_name": None}, headers=headers).status_code == 422
    assert client.patch(url, json={"unknown": 1}, headers=headers).status_code == 422
    assert client.patch(url, json={"email": other["email"]}, headers=headers).status_code == 409


@pytest.mark.parametrize("role", ["user", "office"])
def test_only_admin_changes_roles(client: TestClient, signed_in, role: str):
    user, headers = signed_in(role)

    assert client.patch(f"/users/{user['id']}", json={"role": "admin"}, headers=headers).status_code == 403
    assert client.get("/auth/me", headers=headers).json()["role"] == role


def test_admin_changes_role(client: TestClient, signed_in):
    _, headers = signed_in("admin")
    other = create_user(client)
    other_headers = login(client, other["email"])

    response = client.patch(f"/users/{other['id']}", json={"role": "office"}, headers=headers)

    assert response.json()["role"] == "office"
    # the role is read from the database, so existing tokens get the new role at once.
    assert client.get("/auth/me", headers=other_headers).json()["role"] == "office"
    assert client.patch(f"/users/{other['id']}", json={"role": "boss"}, headers=headers).status_code == 422
    assert client.patch(f"/users/{other['id']}", json={"role": None}, headers=headers).status_code == 422


def test_delete_own_account(client: TestClient, signed_in):
    user, headers = signed_in("user")

    assert client.delete(f"/users/{user['id']}", headers=headers).status_code == 204


def test_delete_user_with_reports_conflicts(client: TestClient, signed_in, connection: psycopg.Connection):
    user, headers = signed_in("user")
    connection.execute(
        "INSERT INTO reports (user_id, description, location) "
        "VALUES (%s, 'Dziura w jezdni', ST_MakePoint(19.9449, 50.0647)::geography)",
        (user["id"],),
    )

    assert client.delete(f"/users/{user['id']}", headers=headers).status_code == 409
    assert client.get(f"/users/{user['id']}", headers=headers).status_code == 200
