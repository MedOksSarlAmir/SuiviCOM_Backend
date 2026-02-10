from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.supervisor import purchase_controller

purchase_bp = Blueprint("purchases", __name__)


@purchase_bp.route("", methods=["GET"])
@jwt_required()
def get_purchases():
    return purchase_controller.list_purchases()


@purchase_bp.route("", methods=["POST"])
@jwt_required()
def add_purchase():
    return purchase_controller.create_purchase()

@purchase_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_purchase(id):
    return purchase_controller.update_purchase(id)

@purchase_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_purchase(id):
    return purchase_controller.delete_purchase(id)



@purchase_bp.route("/matrix", methods=["GET"])
@jwt_required()
def get_purchase_matrix():
    return purchase_controller.get_purchase_matrix()