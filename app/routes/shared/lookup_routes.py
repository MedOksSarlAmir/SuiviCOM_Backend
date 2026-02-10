from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.shared import lookup_controller

lookup_bp = Blueprint("lookups", __name__)


@lookup_bp.route("/admin-metadata", methods=["GET"])
@jwt_required()
def admin_meta():
    return lookup_controller.get_admin_metadata()


@lookup_bp.route("/distributors", methods=["GET"])  # For supervisor dropdowns
@jwt_required()
def scoped_dists():
    return lookup_controller.get_distributors_scoped()


@lookup_bp.route("/products", methods=["GET"])  # For supervisor dropdowns
@jwt_required()
def products_lookup():
    return lookup_controller.get_products_lookup()


@lookup_bp.route("/vendors/distributor/<int:dist_id>", methods=["GET"])
@jwt_required()
def vendors_by_dist(dist_id):
    return lookup_controller.get_vendors_by_distributor(dist_id)


@lookup_bp.route("/categories-with-formats", methods=["GET"])
@jwt_required()
def cat_formats():
    return lookup_controller.get_categories_with_formats()


@lookup_bp.route("/geography", methods=["GET"])
@jwt_required()
def geo_tree():
    return lookup_controller.get_geography_tree()
