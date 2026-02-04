import pytest
import uuid
from app.models import User
from app.extensions import bcrypt


def test_app_health(client):
    response = client.get("/api/v1/auth/app_health")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"


def test_login_success(client, db, app):
    unique_name = f"user_{uuid.uuid4().hex[:5]}"
    with app.app_context():
        hashed = bcrypt.generate_password_hash("secret").decode("utf-8")
        user = User(username=unique_name, password_hash=hashed, role="superviseur")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"username": unique_name, "password": "secret"}
    )
    assert response.status_code == 200
    assert "token" in response.json


def test_login_invalid_credentials(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "wrong", "password": "wrong"},
    )
    assert response.status_code == 401


def test_me_endpoint(client, auth_headers):
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": auth_headers["Authorization"]}
    )
    assert response.status_code == 200
    assert response.json["username"] == auth_headers["username"]
