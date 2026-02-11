from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.supervisor import inventory_controller

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/stock", methods=["GET"])
@jwt_required()
def get_stock():
    return inventory_controller.get_current_stock()


@inventory_bp.route("/adjust", methods=["POST"])
@jwt_required()
def adjust():
    return inventory_controller.adjust_stock()

@inventory_bp.route("/adjust/<int:adj_id>", methods=["DELETE"])
@jwt_required()
def delete_adjustment(adj_id):
    return inventory_controller.delete_adjustment(adj_id)

@inventory_bp.route("/history/<int:dist_id>/<int:prod_id>", methods=["GET"])
@jwt_required()
def get_history(dist_id, prod_id):
    return inventory_controller.get_history(dist_id, prod_id)

@inventory_bp.route("/refresh", methods=["POST"])
@jwt_required()
def refresh():
    return inventory_controller.refresh_inventory()

@inventory_bp.route("/physical", methods=["POST"])
@jwt_required()
def save_physical():
    return inventory_controller.upsert_physical_inventory()