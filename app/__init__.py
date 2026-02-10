from flask import Flask, request
from app.extensions import db, jwt, ma, bcrypt, cors
from app.config import Config
from sqlalchemy import text
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 1. Initialize extensions properly
    db.init_app(app)
    jwt.init_app(app)
    ma.init_app(app)
    bcrypt.init_app(app)

    # Configure CORS - set this to your frontend URL
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": "http://localhost:3000"}},
        supports_credentials=True,
    )

    # 2. Database User Context (SQL Server Session Context)
    @app.before_request
    def set_db_user_context():
        if request.method == "OPTIONS":
            return

        # List of paths that don't need the DB context (no user yet)
        if request.path.startswith("/api/auth/login"):
            return

        if "Authorization" in request.headers:
            try:
                # Check for token without crashing if it's missing or expired
                verify_jwt_in_request(optional=True)
                uid = get_jwt_identity()

                if uid:
                    # Sets the user_id in MSSQL session for RLS or Auditing
                    db.session.execute(
                        text(
                            "EXEC sp_set_session_context @key=N'user_id', @value=:val"
                        ),
                        {"val": uid},
                    )
            except Exception as e:
                app.logger.error(f"Context error: {e}")
                pass

    # 3. Register Blueprints (The New Granular Structure)

    # Auth & Common Lookups
    from app.routes.shared.auth_routes import auth_bp
    from app.routes.shared.lookup_routes import lookup_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(lookup_bp, url_prefix="/api/shared")

    # Admin Management
    from app.routes.admin import admin_group_bp

    app.register_blueprint(admin_group_bp, url_prefix="/api/admin")

    # Supervisor Operations
    from app.routes.supervisor import supervisor_group_bp

    app.register_blueprint(supervisor_group_bp, url_prefix="/api/supervisor")

    return app
