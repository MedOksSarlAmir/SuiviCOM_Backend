from flask import Blueprint
from .user_routes import user_bp
from .distributor_routes import distributor_bp
from .product_routes import product_bp
from .geo_routes import geo_bp

admin_group_bp = Blueprint("admin_group", __name__)

# Register sub-blueprints
admin_group_bp.register_blueprint(user_bp, url_prefix="/users")
admin_group_bp.register_blueprint(distributor_bp, url_prefix="/distributors")
admin_group_bp.register_blueprint(product_bp, url_prefix="/products")
admin_group_bp.register_blueprint(geo_bp, url_prefix="/geography")
