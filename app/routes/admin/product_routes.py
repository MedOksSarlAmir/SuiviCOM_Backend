from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.admin import product_controller
from app.utils.decorators import roles_required

product_bp = Blueprint("products", __name__)


@product_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("admin")
def list_prods():
    return product_controller.list_products()


@product_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin")
def create_prod():
    return product_controller.create_product()


@product_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
@roles_required("admin")
def update_prod(id):
    return product_controller.update_product(id)
