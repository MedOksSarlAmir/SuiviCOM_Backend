from flask import Blueprint
from .sale_routes import sale_bp
from .purchase_routes import purchase_bp
from .visit_routes import visit_bp
from .inventory_routes import inventory_bp
from .dashboard_routes import dashboard_bp
from .vendor_routes import vendor_bp

supervisor_group_bp = Blueprint("supervisor_group", __name__)

supervisor_group_bp.register_blueprint(sale_bp, url_prefix="/sales")
supervisor_group_bp.register_blueprint(purchase_bp, url_prefix="/purchases")
supervisor_group_bp.register_blueprint(visit_bp, url_prefix="/visits")
supervisor_group_bp.register_blueprint(inventory_bp, url_prefix="/inventory")
supervisor_group_bp.register_blueprint(
    dashboard_bp, url_prefix="/dashboard"
)
supervisor_group_bp.register_blueprint(vendor_bp, url_prefix="/vendors")