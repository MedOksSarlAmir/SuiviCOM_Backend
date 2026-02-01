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