from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers import supervisor_controller

supervisor_bp = Blueprint("supervisor", __name__)


@supervisor_bp.route("/distributors", methods=["GET"])
@jwt_required()
def distributors():
    return supervisor_controller.get_distributors()


@supervisor_bp.route("/vendors/distributor/<int:dist_id>", methods=["GET"])
@jwt_required()
def vendors(dist_id):
    return supervisor_controller.get_vendors_by_distributor(dist_id)


@supervisor_bp.route("/products", methods=["GET"])
@jwt_required()
def products():
    return supervisor_controller.get_products()


# --- NEW FILTER ENDPOINTS ---


@supervisor_bp.route("/categories-with-formats", methods=["GET"])
@jwt_required()
def categories_with_formats():
    return supervisor_controller.get_categories_with_formats()


@supervisor_bp.route("/types", methods=["GET"])
@jwt_required()
def types():
    return supervisor_controller.get_product_types()
