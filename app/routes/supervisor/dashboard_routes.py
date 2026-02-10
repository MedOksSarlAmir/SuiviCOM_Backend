from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.supervisor import dashboard_controller

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/stats", methods=["GET"])
@jwt_required()
def stats():
    return dashboard_controller.get_stats()
