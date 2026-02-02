from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import Vendor, Sale, User, Visit
from sqlalchemy import or_


def get_vendors():
    uid = get_jwt_identity()
    user = User.query.get(uid)

    query = Vendor.query

    # 1. Scoping: Supervisors only see vendors assigned to them
    if user.role == "superviseur":
        query = query.filter_by(supervisor_id=uid)

    # 2. Filtering
    dist_id = request.args.get("distributor_id")
    if dist_id and dist_id != "all":
        query = query.filter_by(distributor_id=dist_id)

    vend_type = request.args.get("vendor_type")
    if vend_type and vend_type != "all":
        query = query.filter_by(vendor_type=vend_type)

    search = request.args.get("search")
    if search:
        query = query.filter(
            or_(
                Vendor.nom.ilike(f"%{search}%"),
                Vendor.prenom.ilike(f"%{search}%"),
                Vendor.code.ilike(f"%{search}%"),
            )
        )

    vendors = query.all()

    return (
        jsonify(
            [
                {
                    "id": v.id,
                    "code": v.code,
                    "nom": v.nom,
                    "prenom": v.prenom,
                    "vendor_type": v.vendor_type,
                    "distributor_id": v.distributor_id,
                    "distributor_nom": v.distributor.nom if v.distributor else "N/A",
                    "active": v.active,
                }
                for v in vendors
            ]
        ),
        200,
    )


def create_vendor():
    uid = get_jwt_identity()
    data = request.json

    try:
        # Check if code already exists (must be unique)
        if Vendor.query.filter_by(code=data["code"]).first():
            return jsonify({"message": "Ce code vendeur est déjà utilisé"}), 400

        new_vendor = Vendor(
            code=data["code"],
            nom=data["nom"],
            prenom=data["prenom"],
            vendor_type=data.get("vendor_type", "detail"),
            distributor_id=data["distributor_id"],
            supervisor_id=uid,
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


def update_vendor(id):
    vendor = Vendor.query.get_or_404(id)
    data = request.json

    try:
        vendor.code = data.get("code", vendor.code)
        vendor.nom = data.get("nom", vendor.nom)
        vendor.prenom = data.get("prenom", vendor.prenom)
        vendor.vendor_type = data.get("vendor_type", vendor.vendor_type)
        vendor.active = data.get("active", vendor.active)
        vendor.distributor_id = data.get("distributor_id", vendor.distributor_id)

        db.session.commit()
        return jsonify({"message": "Vendeur mis à jour"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def delete_vendor(id):
    vendor = Vendor.query.get_or_404(id)

    # Check if the vendor has any related records
    sales_count = Sale.query.filter_by(vendor_id=id).count()
    visits_count = Visit.query.filter_by(vendor_id=id).count()

    if sales_count > 0 or visits_count > 0:
        reasons = []
        if sales_count > 0:
            reasons.append(f"{sales_count} vente(s) enregistrée(s)")
        if visits_count > 0:
            reasons.append(f"{visits_count} visite(s) programmée(s)")

        return (
            jsonify(
                {
                    "message": (
                        f"Impossible de supprimer ce vendeur: " +
                        ", ".join(reasons) +
                        ". Veuillez le désactiver à la place."
                    )
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
