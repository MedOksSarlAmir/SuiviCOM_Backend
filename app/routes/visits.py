from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers import visits_controller

visits_bp = Blueprint("visits", __name__)


@visits_bp.route("", methods=["GET"])
@jwt_required()
def index():
    return visits_controller.get_visits()


@visits_bp.route("", methods=["POST"])
@jwt_required()
def store():
    return visits_controller.create_visit()


@visits_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update(id):
    return visits_controller.update_visit(id)


@visits_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def destroy(id):
    return visits_controller.delete_visit(id)
