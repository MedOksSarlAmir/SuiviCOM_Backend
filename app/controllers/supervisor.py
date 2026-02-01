from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import Distributor, Vendor, Product, User, ProductView, DistributorView


def get_distributors():
    uid = get_jwt_identity()
    user = User.query.get(uid)

    query = DistributorView.query.filter_by(active=True)

    # Scoping
    if user.role == "superviseur":
        query = query.filter_by(supervisor_id=uid)

    return (
        jsonify(
            [{"id": d.id, "nom": d.nom, "wilaya": d.wilaya_nom} for d in query.all()]
        ),
        200,
    )


def get_products():
    prods = ProductView.query.filter_by(active=True).all()

    return (
        jsonify(
            [
                {
                    "id": p.id,
                    "code": p.code,
                    "designation": p.designation,
                    "price_factory": float(p.price_factory or 0),
                    "price_gros": float(p.price_gros or 0),
                    "price_detail": float(p.price_detail or 0),
                    "price_superette": float(p.price_superette or 0),
                    "category": p.category_name,
                }
                for p in prods
            ]
        ),
        200,
    )


def get_vendors_by_distributor(dist_id):
    distributor = Distributor.query.get_or_404(dist_id)

    vendors = sorted(distributor.vendors, key=lambda v: not v.active)

    return (
        jsonify(
            [
                {
                    "id": v.id,
                    "nom": v.nom,
                    "prenom": v.prenom,
                    "code": v.code,
                    "type": v.vendor_type,
                    "active": v.active,
                }
                for v in vendors
            ]
        ),
        200,
    )
