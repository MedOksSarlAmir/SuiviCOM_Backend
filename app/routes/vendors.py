from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers import vendors as vendor_controller

vendors_bp = Blueprint("vendors", __name__)


@vendors_bp.route("", methods=["GET"])
@jwt_required()
def index():
    return vendor_controller.get_vendors()


@vendors_bp.route("", methods=["POST"])
@jwt_required()
def store():
    return vendor_controller.create_vendor()


@vendors_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update(id):
    return vendor_controller.update_vendor(id)


@vendors_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def destroy(id):
    return vendor_controller.delete_vendor(id)
