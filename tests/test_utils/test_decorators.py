import pytest
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, create_access_token
from app.utils.decorators import roles_required


def test_roles_required_decorator():
    """Test the roles_required decorator"""
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = "test-secret"
    jwt = JWTManager(app)

    @app.route("/admin-only")
    @roles_required("admin")
    def admin_only():
        return jsonify({"message": "Admin access granted"})

    @app.route("/supervisor-or-admin")
    @roles_required("superviseur", "admin")
    def supervisor_or_admin():
        return jsonify({"message": "Access granted"})

    client = app.test_client()

    # Test without token
    response = client.get("/admin-only")
    assert response.status_code == 401  # JWT would normally catch this

    # Note: Full integration test would require a proper Flask app context
    # This tests the decorator logic in isolation


def test_roles_required_logic():
    """Test the decorator logic with mocked JWT"""
    from unittest.mock import Mock

    # Mock flask_jwt_extended.get_jwt
    import app.utils.decorators as decorators_module

    # Test allowed role
    mock_get_jwt = Mock(return_value={"role": "admin"})
    decorators_module.get_jwt = mock_get_jwt

    mock_fn = Mock(return_value="success")
    decorated = decorators_module.roles_required("admin", "superviseur")(mock_fn)

    result = decorated()
    assert result == "success"
    mock_fn.assert_called_once()

    # Test disallowed role
    mock_get_jwt = Mock(return_value={"role": "user"})
    decorators_module.get_jwt = mock_get_jwt

    mock_fn = Mock(return_value="success")
    decorated = decorators_module.roles_required("admin", "superviseur")(mock_fn)

    result = decorated()
    assert result[1] == 403  # Forbidden
    mock_fn.assert_not_called()

    # Test no role in JWT
    mock_get_jwt = Mock(return_value={})
    decorators_module.get_jwt = mock_get_jwt

    mock_fn = Mock(return_value="success")
    decorated = decorators_module.roles_required("admin")(mock_fn)

    result = decorated()
    assert result[1] == 403
    mock_fn.assert_not_called()
