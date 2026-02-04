import pytest
import jwt
import time
from flask_jwt_extended import decode_token
from app.extensions import jwt as jwt_manager


def test_jwt_token_structure(client, auth_headers):
    """Test JWT token has correct structure"""
    token = auth_headers["Authorization"].replace("Bearer ", "")
    decoded = jwt.decode(token, options={"verify_signature": False})

    # FIX: 'sub' is the standard field for identity in Flask-JWT-Extended
    assert "sub" in decoded
    assert "role" in decoded
    assert decoded["role"] == "superviseur"


def test_expired_token(client, app, db):
    """Test that expired tokens are rejected"""
    from flask_jwt_extended import create_access_token
    from app.models import User

    # Create user
    user = User(
        username=f"exp_test_{time.time()}",
        password_hash="hash",
        role="superviseur",
    )
    db.session.add(user)
    db.session.commit()

    # Create token with immediate expiration
    with app.app_context():
        token = create_access_token(
            identity=str(user.id),
            additional_claims={"role": "superviseur"},
            expires_delta=0,  # Expires immediately
        )

    # Wait a bit
    time.sleep(1)

    # Try to use expired token
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    # Should be unauthorized
    assert response.status_code == 401


def test_tampered_token(client):
    """Test that tampered tokens are rejected"""
    # Create a valid-looking but tampered token
    tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"}
    )

    assert response.status_code == 401


def test_missing_token(client):
    """Test endpoints that require authentication without token"""
    endpoints = [
        "/api/v1/dashboard/stats",
        "/api/v1/sales",
        "/api/v1/purchases",
        "/api/v1/inventory/1",
        "/api/v1/vendors",
        "/api/v1/visits",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401


def test_token_with_wrong_role(client, app, db):
    """Test token with role that doesn't match user in DB"""
    from flask_jwt_extended import create_access_token
    from app.models import User
    from app.extensions import bcrypt

    # Create user with one role
    username = f"role_test_{time.time()}"
    user = User(
        username=username,
        password_hash=bcrypt.generate_password_hash("password").decode("utf-8"),
        role="superviseur",  # Actual role in DB
    )
    db.session.add(user)
    db.session.commit()

    # Create token with different role claim
    with app.app_context():
        token = create_access_token(
            identity=str(user.id),
            additional_claims={"role": "admin"},  # Wrong role in token
        )

    # This should still work because we trust the token claims
    # The me endpoint gets user from DB, not from token claims
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    # User role from DB should be returned, not from token
    assert response.json["role"] == "superviseur"
