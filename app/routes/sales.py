from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers import sales_controller

sales_bp = Blueprint("sales", __name__)


@sales_bp.route("", methods=["GET"])
@jwt_required()
def index():
    return sales_controller.get_sales()


@sales_bp.route("", methods=["POST"])
@jwt_required()
def store():
    return sales_controller.create_sale()


@sales_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update(id):
    return sales_controller.update_sale(id)


@sales_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def destroy(id):
    return sales_controller.delete_sale(id)


@sales_bp.route("/weekly-matrix", methods=["GET"])
@jwt_required()
def weekly_matrix():
    return sales_controller.get_weekly_sales_matrix()


@sales_bp.route("/upsert-item", methods=["POST"])
@jwt_required()
def upsert_item():
    return sales_controller.upsert_sale_item()


@sales_bp.route("/update-status", methods=["POST"])
@jwt_required()
def update_status():
    from app.controllers import sales_controller

    return sales_controller.update_sale_status_by_date()
