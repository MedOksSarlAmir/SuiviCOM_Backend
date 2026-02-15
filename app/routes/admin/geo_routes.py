from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.controllers.admin import geo_controller
from app.utils.decorators import roles_required

geo_bp = Blueprint("admin_geo", __name__)


# Regions
@geo_bp.route("/regions", methods=["GET"])
@jwt_required()
def get_regs():
    return geo_controller.list_regions()


@geo_bp.route("/regions", methods=["POST"])
@jwt_required()
@roles_required("admin")
def post_reg():
    return geo_controller.create_region()


@geo_bp.route("/regions/<int:id>", methods=["DELETE"])
@jwt_required()
@roles_required("admin")
def del_reg(id):
    return geo_controller.delete_region(id)


# Zones
@geo_bp.route("/zones", methods=["GET"])
@jwt_required()
def get_zones():
    return geo_controller.list_zones()


@geo_bp.route("/zones", methods=["POST"])
@jwt_required()
@roles_required("admin")
def post_zone():
    return geo_controller.create_zone()


@geo_bp.route("/zones/<int:id>", methods=["DELETE"])
@jwt_required()
@roles_required("admin")
def del_zone(id):
    return geo_controller.delete_zone(id)


# Wilayas
@geo_bp.route("/wilayas", methods=["GET"])
@jwt_required()
def get_wils():
    return geo_controller.list_wilayas()


@geo_bp.route("/wilayas", methods=["POST"])
@jwt_required()
@roles_required("admin")
def post_wil():
    return geo_controller.create_wilaya()


@geo_bp.route("/wilayas/<int:id>", methods=["DELETE"])
@jwt_required()
@roles_required("admin")
def del_wil(id):
    return geo_controller.delete_wilaya(id)
