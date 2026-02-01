from flask import Flask, request
from app.extensions import db, jwt, ma, bcrypt, cors  # Use these!
from app.config import Config
from sqlalchemy import text
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions properly
    db.init_app(app)
    jwt.init_app(app)
    ma.init_app(app)
    bcrypt.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": "http://localhost:3000"}},
        supports_credentials=True,
    )

    @app.before_request
    def set_db_user_context():
        # 1. Skip for Pre-flight (CORS)
        if request.method == "OPTIONS":
            return

        # 2. Skip for Login/Auth routes
        # We don't want to run DB context logic when the user is trying to get a token
        if request.path.startswith("/api/v1/auth"):
            return

        # 3. Only run if an Authorization header is actually present
        if "Authorization" in request.headers:
            try:
                # verify_jwt_in_request can throw errors if token is expired/invalid
                verify_jwt_in_request(optional=True)
                uid = get_jwt_identity()

                if uid:
                    # Use a clean execution that doesn't interfere with the main transaction
                    db.session.execute(
                        text(
                            "EXEC sp_set_session_context @key=N'user_id', @value=:val"
                        ),
                        {"val": uid},
                    )
            except Exception as e:
                # Log the error but don't crash the app
                app.logger.error(f"Context error: {e}")
                pass

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.sales import sales_bp
    from app.routes.supervisor import supervisor_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.purchases import purchases_bp 
    from app.routes.inventory import inventory_bp 
    from app.routes.visits import visits_bp
    from app.routes.vendors import vendors_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(sales_bp, url_prefix="/api/v1/sales")
    app.register_blueprint(supervisor_bp, url_prefix="/api/v1/supervisor")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(purchases_bp, url_prefix="/api/v1/purchases")
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")
    app.register_blueprint(visits_bp, url_prefix="/api/v1/visits")
    app.register_blueprint(vendors_bp, url_prefix="/api/v1/vendors")

    return app