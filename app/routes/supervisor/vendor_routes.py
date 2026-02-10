from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.supervisor import vendor_controller

vendor_bp = Blueprint("vendors", __name__)


@vendor_bp.route("", methods=["GET"])
@jwt_required()
def get_vendors():
    return vendor_controller.list_vendors()


@vendor_bp.route("", methods=["POST"])
@jwt_required()
def add_vendor():
    return vendor_controller.create_vendor()


@vendor_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_vendor(id):
    return vendor_controller.update_vendor(id)

@vendor_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_vendor(id):
    return vendor_controller.delete_vendor(id)