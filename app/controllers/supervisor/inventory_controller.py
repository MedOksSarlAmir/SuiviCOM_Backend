from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import (
    Inventory,
    InventoryHistoryView,
    StockAdjustment,
    Product,
    User,
    Distributor
)
from app.utils.stock_ops import update_stock_incremental
from app.utils.pagination import paginate
from datetime import datetime
from sqlalchemy import text, or_


def get_current_stock():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    dist_id = request.args.get("distributor_id", type=int)
    search = request.args.get("search", "")

    # 🔹 RESTORED DATA SCOPING
    if user and user.role == "superviseur":
        assigned_distributors = Distributor.query.filter_by(supervisor_id=uid).all()
        assigned_ids = [d.id for d in assigned_distributors]

        if not assigned_ids:
            return jsonify({"data": [], "message": "Aucun distributeur assigné"}), 200

        if not dist_id or dist_id not in assigned_ids:
            dist_id = assigned_ids[0]  # Default to first allowed

    if not dist_id:
        return jsonify({"data": [], "message": "Aucun distributeur sélectionné"}), 400

    # 🔹 RESTORED SEARCH & JOIN
    query = Inventory.query.join(Product).filter(Inventory.distributor_id == dist_id)

    if search:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.code.ilike(f"%{search}%"),
            )
        )

    paginated = paginate(query.order_by(Product.name.asc()))

    return (
        jsonify(
            {
                "data": [
                    {
                        "product_id": i.product_id,
                        "product_name": i.product.name,
                        "product_code": i.product.code,
                        "category": (
                            i.product.category.name if i.product.category else "N/A"
                        ),
                        "quantity": i.quantity,
                        "last_updated": (
                            i.last_updated.isoformat() if i.last_updated else None
                        ),
                    }
                    for i in paginated["items"]
                ],
                "total": paginated["total"],
                "current_distributor": dist_id,
            }
        ),
        200,
    )


def adjust_stock():
    uid = get_jwt_identity()
    data = request.json

    try:
        qty = int(data["quantity"])
        dist_id = data["distributor_id"]
        prod_id = data["product_id"]

        adj = StockAdjustment(
            date=datetime.now().date(),
            distributor_id=dist_id,
            product_id=prod_id,
            supervisor_id=uid,
            quantity=qty,
            note=data.get("note", "Manual adjustment"),
        )
        db.session.add(adj)

        # Apply change
        update_stock_incremental(dist_id, prod_id, qty)

        db.session.commit()
        return jsonify({"message": "Ajustement enregistré"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500

def delete_adjustment(adj_id):
    adj = StockAdjustment.query.get_or_404(adj_id)

    try:
        update_stock_incremental(
            adj.distributor_id,
            adj.product_id,
            -adj.quantity,
        )

        db.session.delete(adj)
        db.session.commit()
        return jsonify({"message": "Ajustement supprimé"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500

def get_history(dist_id, prod_id):
    query = InventoryHistoryView.query.filter_by(
        distributor_id=dist_id, product_id=prod_id
    )
    paginated = paginate(query.order_by(InventoryHistoryView.date.desc()))

    return (
        jsonify(
            {
                "data": [
                    {
                        "id" : h.ref_id,
                        "date": h.date.isoformat(),
                        "type": h.type,
                        "quantity": h.quantity,
                        "actor": h.actor_name,
                        "note": h.note,
                    }
                    for h in paginated["items"]
                ],
                "total": paginated["total"],
            }
        ),
        200,
    )


def refresh_inventory():
    """Triggers the Stored Procedure to rebuild stock from scratch"""
    try:
        db.session.execute(text("EXEC dbo.sp_refresh_inventory"))
        db.session.commit()
        return jsonify({"message": "Inventaire mis à jour avec succès"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
