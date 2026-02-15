from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import Vendor, User, Distributor
from app.utils.pagination import paginate
from sqlalchemy import or_


def list_vendors():
    uid = get_jwt_identity()
    user = User.query.get(uid)

    query = Vendor.query

    # 🔹 SCOPING: Filter by distributors the supervisor is assigned to
    if user.role == "superviseur":
        dist_ids = [d.id for d in user.supervised_distributors]
        query = query.filter(Vendor.distributor_id.in_(dist_ids))

    # Filters
    dist_id = request.args.get("distributor_id")
    if dist_id and dist_id != "all":
        # Additional security check: if a specific dist_id is requested,
        # ensure supervisor has access to it.
        if user.role == "superviseur" and int(dist_id) not in [
            d.id for d in user.supervised_distributors
        ]:
            return jsonify({"message": "Accès non autorisé à ce distributeur"}), 403
        query = query.filter_by(distributor_id=dist_id)

    vendor_type = request.args.get("vendor_type")
    if vendor_type and vendor_type != "all":
        query = query.filter_by(vendor_type=vendor_type)

    search = request.args.get("search")
    if search:
        query = query.filter(
            or_(
                Vendor.last_name.ilike(f"%{search}%"),
                Vendor.first_name.ilike(f"%{search}%"),
                Vendor.code.ilike(f"%{search}%"),
            )
        )

    paginated = paginate(query.order_by(Vendor.id.desc()))

    return (
        jsonify(
            {
                "data": [
                    {
                        "id": v.id,
                        "code": v.code,
                        "first_name": v.first_name,
                        "last_name": v.last_name,
                        "type": v.vendor_type,
                        "active": v.active,
                        "distributor_name": (
                            v.distributor.name if v.distributor else "N/A"
                        ),
                        "distributor_id": v.distributor_id,
                    }
                    for v in paginated["items"]
                ],
                "total": paginated["total"],
            }
        ),
        200,
    )


def create_vendor():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data = request.json

    dist_id = data.get("distributor_id")

    # 🔹 SECURITY CHECK: Can this supervisor add a vendor to this distributor?
    if user.role == "superviseur" and not user.has_distributor(dist_id):
        return jsonify({"message": "Vous n'êtes pas assigné à ce distributeur"}), 403

    try:
        if Vendor.query.filter_by(code=data["code"]).first():
            return jsonify({"message": "Ce code de vendeur existe déjà"}), 400

        new_vendor = Vendor(
            code=data["code"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            vendor_type=data.get("type", "detail"),
            distributor_id=dist_id,
            supervisor_id=uid,  # Keep track of who created it
            active=True,
        )
        db.session.add(new_vendor)
        db.session.commit()
        return (
            jsonify({"message": "Vendeur créé avec succès", "id": new_vendor.id}),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def update_vendor(vendor_id):
    uid = get_jwt_identity()
    user = User.query.get(uid)
    vendor = Vendor.query.get_or_404(vendor_id)
    data = request.json

    # 🔹 SECURITY CHECK: Verify access to the vendor's distributor
    if user.role == "superviseur" and not user.has_distributor(vendor.distributor_id):
        return jsonify({"message": "Action non autorisée"}), 403

    vendor.first_name = data.get("first_name", vendor.first_name)
    vendor.last_name = data.get("last_name", vendor.last_name)
    vendor.vendor_type = data.get("type", vendor.vendor_type)
    vendor.active = data.get("active", vendor.active)

    db.session.commit()
    return jsonify({"message": "Vendeur mis à jour avec succès"}), 200


def delete_vendor(vendor_id):
    uid = get_jwt_identity()
    user = User.query.get(uid)
    vendor = Vendor.query.get_or_404(vendor_id)

    # 🔹 SECURITY CHECK
    if user.role == "superviseur" and not user.has_distributor(vendor.distributor_id):
        return jsonify({"message": "Action non autorisée"}), 403

    if vendor.sales or vendor.visits_activity:
        return (
            jsonify(
                {
                    "message": "Impossible de supprimer un vendeur ayant des ventes ou des visites. Désactivez-le plutôt."
                }
            ),
            400,
        )

    try:
        db.session.delete(vendor)
        db.session.commit()
        return jsonify({"message": "Vendeur supprimé avec succès"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
