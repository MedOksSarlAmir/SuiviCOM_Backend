from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity
from app.models import (
    ProductCategory,
    ProductType,
    Wilaya,
    User,
    Distributor,
    DistributorView,
    Region,
    Zone,
    Product,
    Vendor,
)
from app.extensions import db


def get_admin_metadata():
    """Dropdowns for Admin panel"""
    supervisors = User.query.filter_by(role="superviseur", active=True).all()
    wilayas = Wilaya.query.all()
    categories = ProductCategory.query.all()
    types = ProductType.query.all()

    return (
        jsonify(
            {
                "supervisors": [
                    {"id": s.id, "name": f"{s.first_name} {s.last_name}"}
                    for s in supervisors
                ],
                "wilayas": [{"id": w.id, "name": w.name} for w in wilayas],
                "categories": [{"id": c.id, "name": c.name} for c in categories],
                "product_types": [{"id": t.id, "name": t.name} for t in types],
            }
        ),
        200,
    )


def get_distributors_scoped():
    """
    FIXED: Uses the Many-to-Many relationship instead of a missing column.
    Returns distributors assigned to the user.
    """
    uid = get_jwt_identity()
    user = User.query.get(uid)

    if not user:
        return jsonify({"message": "Utilisateur non trouvé"}), 404

    # 🔹 If Supervisor: Get from junction table
    if user.role == "superviseur":
        dists = [d for d in user.supervised_distributors if d.active]
    else:
        # 🔹 Admin/DG/DC see all active distributors
        dists = Distributor.query.filter_by(active=True).all()

    return (
        jsonify(
            [
                {
                    "id": d.id,
                    "name": d.name,
                    "wilaya": d.wilaya.name if d.wilaya else "N/A",
                }
                for d in dists
            ]
        ),
        200,
    )


def get_products_lookup():
    """Returns products with all price types"""
    prods = Product.query.filter_by(active=True).all()
    return (
        jsonify(
            [
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "price_factory": float(p.price_factory or 0),
                    "price_wholesale": float(p.price_wholesale or 0),
                    "price_retail": float(p.price_retail or 0),
                    "price_supermarket": float(p.price_supermarket or 0),
                    "category": p.category.name if p.category else "N/A",
                }
                for p in prods
            ]
        ),
        200,
    )


def get_vendors_by_distributor(dist_id):
    """Fetches vendors for a specific distributor"""
    distributor = Distributor.query.get_or_404(dist_id)
    vendors = sorted(distributor.vendors, key=lambda v: not v.active)
    return (
        jsonify(
            [
                {
                    "id": v.id,
                    "name": f"{v.first_name} {v.last_name}",
                    "code": v.code,
                    "type": v.vendor_type,
                    "active": v.active,
                }
                for v in vendors
            ]
        ),
        200,
    )


def get_categories_with_formats():
    """Hierarchical list of categories and their available formats"""
    query_data = (
        db.session.query(ProductCategory.id, ProductCategory.name, Product.format)
        .join(Product, Product.category_id == ProductCategory.id)
        .filter(Product.active == True)
        .distinct()
        .all()
    )
    structured = {}
    for cat_id, cat_name, p_format in query_data:
        if cat_id not in structured:
            structured[cat_id] = {"id": cat_id, "name": cat_name, "formats": []}
        if p_format and p_format not in structured[cat_id]["formats"]:
            structured[cat_id]["formats"].append(p_format)

    return jsonify(sorted(list(structured.values()), key=lambda x: x["name"])), 200


def get_geography_tree():
    regions = Region.query.all()
    return (
        jsonify(
            {
                "regions": [{"id": r.id, "name": r.name} for r in regions],
                "zones": [
                    {"id": z.id, "name": z.name, "region_id": z.region_id}
                    for z in Zone.query.all()
                ],
                "wilayas": [
                    {"id": w.id, "name": w.name, "zone_id": w.zone_id}
                    for w in Wilaya.query.all()
                ],
            }
        ),
        200,
    )
