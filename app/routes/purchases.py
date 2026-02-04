# app/routes/purchases.py
from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers import purchases_controller

purchases_bp = Blueprint("purchases", __name__)

@purchases_bp.route("", methods=["GET"])
@jwt_required()
def index():
    return purchases_controller.get_purchases()

@purchases_bp.route("", methods=["POST"])
@jwt_required()
def store():
    return purchases_controller.create_purchase()

@purchases_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update(id):
    return purchases_controller.update_purchase(id)

@purchases_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def destroy(id):
    return purchases_controller.delete_purchase(id)

@purchases_bp.route("/matrix", methods=["GET"])
@jwt_required()
def get_matrix():
    return purchases_controller.get_purchase_matrix()