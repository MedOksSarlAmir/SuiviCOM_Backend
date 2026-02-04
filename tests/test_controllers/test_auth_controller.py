import pytest
import uuid
from app.extensions import bcrypt


def test_login_with_email_username_extraction(client, db, app):
    """Test login with email (username extraction)"""
    username = f"user_{uuid.uuid4().hex[:5]}"
    with app.app_context():
        hashed = bcrypt.generate_password_hash("secret").decode("utf-8")
        from app.models import User

        user = User(username=username, password_hash=hashed, role="superviseur")
        db.session.add(user)
        db.session.commit()

    # Login with email format
    response = client.post(
        "/api/v1/auth/login",
        json={"username": f"{username}@company.com", "password": "secret"},
    )
    assert response.status_code == 200
    assert "token" in response.json


def test_login_missing_credentials(client):
    """Test login with missing credentials"""
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 400
    assert "Données manquantes" in response.json["message"]

    response = client.post("/api/v1/auth/login", json={"username": "test"})
    assert response.status_code == 400

    response = client.post("/api/v1/auth/login", json={"password": "test"})
    assert response.status_code == 400


def test_login_user_not_found(client):
    """Test login with non-existent user"""
    response = client.post(
        "/api/v1/auth/login", json={"username": "nonexistent", "password": "wrong"}
    )
    assert response.status_code == 401


def test_me_endpoint_no_user(client, auth_headers, db):
    """Test /me endpoint when user doesn't exist (edge case)"""
    # Delete the user from DB but keep token
    from app.models import User

    user_id = auth_headers["user_id"]
    User.query.filter_by(id=user_id).delete()
    db.session.commit()

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": auth_headers["Authorization"]}
    )
    assert response.status_code == 404
    assert "User not found" in response.json["error"]


def test_check_health_database_down(client, app, monkeypatch):
    """Test health check when database is down"""
    # Mock the database query to raise an exception
    from app.controllers import auth as auth_controller

    def mock_execute(*args, **kwargs):
        raise Exception("Database connection failed")

    monkeypatch.setattr(auth_controller.db.session, "execute", mock_execute)

    response = client.get("/api/v1/auth/app_health")
    assert response.status_code == 500
    assert response.json["status"] == "unhealthy"
    assert response.json["services"]["database"] == "unhealthy"


def test_check_health_success(client):
    """Test successful health check"""
    response = client.get("/api/v1/auth/app_health")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"
    assert response.json["services"]["database"] == "healthy"
