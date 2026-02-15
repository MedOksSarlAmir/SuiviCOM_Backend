from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import Sale, Purchase, Visit, User, Inventory, Product, SaleItem
from sqlalchemy import func, text
from datetime import datetime


def get_stats():
    uid = get_jwt_identity()
    user = User.query.get(uid)

    # 🔹 SCOPING: Extract IDs from the junction table
    dist_ids = [d.id for d in user.supervised_distributors if d.active]

    if not dist_ids:
        return (
            jsonify(
                {
                    "data": {
                        "metrics": {
                            "sales": 0,
                            "purchases": 0,
                            "coverage": 0,
                            "lowStockAlerts": 0,
                        },
                        "rankings": {"vendors": [], "products": []},
                    },
                    "message": "Aucun distributeur assigné",
                }
            ),
            200,
        )

    today = datetime.now()
    first_day = today.replace(day=1, hour=0, minute=0, second=0)

    # Sales & Purchases
    sales_total = (
        db.session.query(func.sum(Sale.total_amount))
        .filter(Sale.distributor_id.in_(dist_ids), Sale.date >= first_day)
        .scalar()
        or 0
    )
    purchases_total = (
        db.session.query(func.sum(Purchase.total_amount))
        .filter(Purchase.distributor_id.in_(dist_ids), Purchase.date >= first_day)
        .scalar()
        or 0
    )

    # Visits Coverage
    v_stats = (
        db.session.query(func.sum(Visit.planned_visits), func.sum(Visit.actual_visits))
        .filter(Visit.distributor_id.in_(dist_ids), Visit.date >= first_day)
        .first()
    )
    planned, actual = v_stats[0] or 0, v_stats[1] or 0
    coverage = round((actual / planned * 100), 1) if planned > 0 else 0

    # Low Stock
    low_stock = Inventory.query.filter(
        Inventory.distributor_id.in_(dist_ids), Inventory.quantity <= 5
    ).count()

    # Top 5 Vendors
    top_vendors = (
        db.session.query(
            func.concat(User.first_name, " ", User.last_name),
            func.sum(Sale.total_amount).label("total"),
        )
        .join(Sale, Sale.vendor_id == User.id)
        .filter(Sale.date >= first_day, Sale.distributor_id.in_(dist_ids))
        .group_by(User.id, User.first_name, User.last_name)
        .order_by(text("total DESC"))
        .limit(5)
        .all()
    )

    # Top 5 Products
    top_products = (
        db.session.query(Product.name, func.sum(SaleItem.quantity).label("qty"))
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.date >= first_day, Sale.distributor_id.in_(dist_ids))
        .group_by(Product.id, Product.name)
        .order_by(text("qty DESC"))
        .limit(5)
        .all()
    )

    return (
        jsonify(
            {
                "data": {
                    "metrics": {
                        "sales": float(sales_total),
                        "purchases": float(purchases_total),
                        "coverage": coverage,
                        "lowStockAlerts": low_stock,
                    },
                    "rankings": {
                        "vendors": [
                            {"name": v[0], "value": float(v[1])} for v in top_vendors
                        ],
                        "products": [
                            {"name": p[0], "value": int(p[1])} for p in top_products
                        ],
                    },
                }
            }
        ),
        200,
    )
