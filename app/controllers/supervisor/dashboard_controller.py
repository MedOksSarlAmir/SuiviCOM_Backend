from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import (
    Sale,
    Purchase,
    Visit,
    Distributor,
    Vendor,
    User,
    Inventory,
    Product,
    SaleItem,
)
from sqlalchemy import func, text
from datetime import datetime


def get_stats():
    uid = get_jwt_identity()
    user = User.query.get(uid)

    # 1. Scoping: Get distributors assigned to this supervisor
    assigned_distributors = Distributor.query.filter_by(
        supervisor_id=uid, active=True
    ).all()
    dist_ids = [d.id for d in assigned_distributors]

    # Maintain the original "empty data" structure if no distributors found
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

    # 2. Time Range (Current Month)
    today = datetime.now()
    first_day = today.replace(day=1, hour=0, minute=0, second=0)

    # --- METRICS CALCULATIONS ---

    # Total Sales (Month) - uses Sale.total_amount (mapped to montant_total)
    sales_total = (
        db.session.query(func.sum(Sale.total_amount))
        .filter(Sale.distributor_id.in_(dist_ids), Sale.date >= first_day)
        .scalar()
        or 0
    )

    # Total Purchases (Month) - uses Purchase.total_amount (mapped to montant_total)
    purchases_total = (
        db.session.query(func.sum(Purchase.total_amount))
        .filter(Purchase.distributor_id.in_(dist_ids), Purchase.date >= first_day)
        .scalar()
        or 0
    )

    # Visit Coverage (Month)
    v_stats = (
        db.session.query(func.sum(Visit.planned_visits), func.sum(Visit.actual_visits))
        .filter(Visit.distributor_id.in_(dist_ids), Visit.date >= first_day)
        .first()
    )
    planned = v_stats[0] or 0
    actual = v_stats[1] or 0
    coverage = round((actual / planned * 100), 1) if planned > 0 else 0

    # Low Stock Alert (Threshold remains <= 5)
    low_stock = Inventory.query.filter(
        Inventory.distributor_id.in_(dist_ids), Inventory.quantity <= 5
    ).count()

    # --- RANKINGS / TOP PERFORMERS ---

    # Top 5 Vendors (Revenue)
    top_vendors = (
        db.session.query(
            Vendor.first_name,
            Vendor.last_name,
            func.sum(Sale.total_amount).label("total"),
        )
        .join(Sale, Sale.vendor_id == Vendor.id)
        .filter(Sale.date >= first_day, Sale.distributor_id.in_(dist_ids))
        .group_by(Vendor.id, Vendor.first_name, Vendor.last_name)
        .order_by(text("total DESC"))
        .limit(5)
        .all()
    )

    # RESTORED: Top 5 Products by Quantity (Month)
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

    # Final Response structure matching original "data" wrapper
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
                            {"name": f"{v[0]} {v[1]}", "value": float(v[2])}
                            for v in top_vendors
                        ],
                        "products": [
                            {"name": v[0], "value": int(v[1])} for v in top_products
                        ],
                    },
                }
            }
        ),
        200,
    )
