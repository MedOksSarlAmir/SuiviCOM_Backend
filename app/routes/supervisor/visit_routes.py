from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.supervisor import visit_controller

visit_bp = Blueprint("visits", __name__)


@visit_bp.route("/matrix", methods=["GET"])
@jwt_required()
def get_matrix():
    return visit_controller.get_visit_matrix()


@visit_bp.route("/upsert", methods=["POST"])
@jwt_required()
def upsert_visit():
    return visit_controller.upsert_visit()
