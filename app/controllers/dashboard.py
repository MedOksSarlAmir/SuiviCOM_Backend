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

    # 1. Get IDs for Scoping (Distributors assigned to this supervisor)
    assigned_distributors = Distributor.query.filter_by(supervisor_id=uid).all()
    dist_ids = [d.id for d in assigned_distributors]

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

    # 2. Time Ranges (Current Month)
    today = datetime.now()
    first_day_month = today.replace(day=1, hour=0, minute=0, second=0)

    # --- METRICS CALCULATIONS ---

    # Total Sales Amount (Month)
    total_sales = (
        db.session.query(func.sum(Sale.montant_total))
        .filter(Sale.distributor_id.in_(dist_ids), Sale.date >= first_day_month)
        .scalar()
        or 0
    )

    # Total Purchases Amount (Month)
    total_purchases = (
        db.session.query(func.sum(Purchase.montant_total))
        .filter(Purchase.distributor_id.in_(dist_ids), Purchase.date >= first_day_month)
        .scalar()
        or 0
    )

    # Visit Coverage (Month)
    visit_stats = (
        db.session.query(
            func.sum(Visit.visites_programmees), func.sum(Visit.visites_effectuees)
        )
        .filter(Visit.distributor_id.in_(dist_ids), Visit.date >= first_day_month)
        .first()
    )

    prog_visits = visit_stats[0] or 0
    eff_visits = visit_stats[1] or 0
    coverage = round((eff_visits / prog_visits * 100), 1) if prog_visits > 0 else 0

    # Low Stock Alert (Count of items with 5 or less units)
    low_stock_count = Inventory.query.filter(
        Inventory.distributor_id.in_(dist_ids), Inventory.stock_qte <= 5
    ).count()

    # --- RANKINGS / TOP PERFORMERS ---

    # Top 5 Vendors by Revenue (Month)
    top_vendors = (
        db.session.query(
            Vendor.nom, Vendor.prenom, func.sum(Sale.montant_total).label("total")
        )
        .join(Sale, Sale.vendor_id == Vendor.id)
        .filter(Sale.date >= first_day_month, Sale.distributor_id.in_(dist_ids))
        .group_by(Vendor.id, Vendor.nom, Vendor.prenom)
        .order_by(text("total DESC"))
        .limit(5)
        .all()
    )

    # Top 5 Selling Products by Quantity (Month)
    top_products = (
        db.session.query(Product.designation, func.sum(SaleItem.quantity).label("qty"))
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.date >= first_day_month, Sale.distributor_id.in_(dist_ids))
        .group_by(Product.id, Product.designation)
        .order_by(text("qty DESC"))
        .limit(5)
        .all()
    )

    return (
        jsonify(
            {
                "data": {
                    "metrics": {
                        "sales": float(total_sales),
                        "purchases": float(total_purchases),
                        "coverage": coverage,
                        "lowStockAlerts": low_stock_count,
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
