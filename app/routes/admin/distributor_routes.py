from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.admin import distributor_controller
from app.utils.decorators import roles_required

distributor_bp = Blueprint("distributors", __name__)


@distributor_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("admin")
def list_dists():
    return distributor_controller.list_distributors()


@distributor_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin")
def create_dist():
    return distributor_controller.create_distributor()


@distributor_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
@roles_required("admin")
def update_dist(id):
    return distributor_controller.update_distributor(id)


@distributor_bp.route("/bulk-reassign", methods=["POST"])
@jwt_required()
@roles_required("admin")
def reassign():
    return distributor_controller.bulk_reassign()


@distributor_bp.route("/supervisors", methods=["GET"])
@jwt_required()
@roles_required("admin")
def list_supervisors():
    return distributor_controller.list_supervisors()
