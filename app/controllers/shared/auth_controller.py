from flask import request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity
from sqlalchemy import text
from app.extensions import bcrypt, db
from app.models import User

def login():
    data = request.get_json() or {}

    identifier = data.get("username") or data.get("email")
    password = data.get("password")

    if not identifier or not password:
        return jsonify({"message": "Données manquantes"}), 400

    # If frontend sends an email, extract username
    if "@" in identifier:
        identifier = identifier.split("@")[0]

    user = User.query.filter_by(username=identifier).first()

    if user and bcrypt.check_password_hash(user.password_hash, password):
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={"role": user.role},
        )

        return (
            jsonify(
                {
                    "token": access_token,
                    "user": user.to_dict(),
                }
            ),
            200,
        )

    return jsonify({"message": "Identifiants invalides"}), 401


def me():
    uid = get_jwt_identity()
    user = User.query.get(int(uid))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict())


def check_health():
    health_status = {"status": "healthy", "services": {"database": "unhealthy"}}

    try:
        # Perform a simple query to verify DB connectivity
        db.session.execute(text("SELECT 1"))
        health_status["services"]["database"] = "healthy"
        return jsonify(health_status), 200
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        return jsonify(health_status), 500