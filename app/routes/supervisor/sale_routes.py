from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.supervisor import sale_controller

sale_bp = Blueprint("sales", __name__)


@sale_bp.route("", methods=["GET"])
@jwt_required()
def get_sales():
    return sale_controller.list_sales()


@sale_bp.route("/matrix", methods=["GET"])
@jwt_required()
def get_matrix():
    return sale_controller.get_weekly_matrix()


@sale_bp.route("/upsert", methods=["POST"])
@jwt_required()
def upsert_item():
    return sale_controller.upsert_sale_item()


@sale_bp.route("/status", methods=["POST"])
@jwt_required()
def update_status():
    return sale_controller.update_sale_status_by_date()


@sale_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_sale(id):
    return sale_controller.update_sale(id)


@sale_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_sale(id):
    return sale_controller.delete_sale(id)

@sale_bp.route("/bulk-upsert", methods=["POST"])
@jwt_required()
def bulk_upsert_sales():
    return sale_controller.bulk_upsert_sale_items()