from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers import inventory as inventory_controller
from app.utils.decorators import roles_required

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/<int:dist_id>", methods=["GET"])
@jwt_required()
def get_inventory(dist_id):
    return inventory_controller.get_inventory(dist_id)


@inventory_bp.route("/refresh", methods=["POST"])
@jwt_required()
def refresh_inventory():
    return inventory_controller.refresh_inventory_data()


@inventory_bp.route("/history/<int:dist_id>/<int:prod_id>", methods=["GET"])
@jwt_required()
def get_history(dist_id, prod_id):
    return inventory_controller.get_product_history(dist_id, prod_id)


@inventory_bp.route("/adjust/<int:prod_id>", methods=["POST"])
@jwt_required()
def adjust_stock(prod_id):
    return inventory_controller.create_adjustment(prod_id)


@inventory_bp.route("/adjust/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_adjust(id):
    return inventory_controller.delete_adjustment(id)
