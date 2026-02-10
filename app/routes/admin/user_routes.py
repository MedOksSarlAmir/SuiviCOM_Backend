from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.admin import user_controller
from app.utils.decorators import roles_required

user_bp = Blueprint("users", __name__)


@user_bp.route("", methods=["GET"])
@jwt_required()
@roles_required("admin")
def get_users():
    return user_controller.list_users()


@user_bp.route("", methods=["POST"])
@jwt_required()
@roles_required("admin")
def add_user():
    return user_controller.create_user()


@user_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
@roles_required("admin")
def update_user(id):
    return user_controller.update_user(id)


@user_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
@roles_required("admin")
def delete_user(id):
    return user_controller.delete_user(id)
