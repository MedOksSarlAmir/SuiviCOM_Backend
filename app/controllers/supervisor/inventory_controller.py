from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import (
    Inventory,
    InventoryHistoryView,
    StockAdjustment,
    Product,
    User,
    Distributor,
    PhysicalInventory,
)
from app.utils.stock_ops import update_stock_incremental
from app.utils.pagination import paginate
from datetime import datetime
from sqlalchemy import and_, text, or_


def get_current_stock():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    dist_id = request.args.get("distributor_id", type=int)
    search = request.args.get("search", "")

    # 🔹 SCOPING: Use the junction relationship
    if user.role == "superviseur":
        assigned_ids = [d.id for d in user.supervised_distributors]
        if not assigned_ids:
            return jsonify({"data": [], "message": "Aucun distributeur assigné"}), 200
        if not dist_id or dist_id not in assigned_ids:
            dist_id = assigned_ids[0]

    if not dist_id:
        return jsonify({"data": [], "message": "Distributeur requis"}), 400

    query = (
        db.session.query(Inventory, PhysicalInventory.quantity.label("physical_qty"))
        .join(Product, Inventory.product_id == Product.id)
        .outerjoin(
            PhysicalInventory,
            and_(
                PhysicalInventory.distributor_id == Inventory.distributor_id,
                PhysicalInventory.product_id == Inventory.product_id,
            ),
        )
        .filter(Inventory.distributor_id == dist_id)
    )

    if search:
        query = query.filter(
            or_(Product.name.ilike(f"%{search}%"), Product.code.ilike(f"%{search}%"))
        )

    paginated = paginate(query.order_by(Product.name.asc()))

    return (
        jsonify(
            {
                "data": [
                    {
                        "product_id": item.Inventory.product_id,
                        "product_name": item.Inventory.product.name,
                        "product_code": item.Inventory.product.code,
                        "theoretical_qty": item.Inventory.quantity,
                        "physical_qty": (
                            item.physical_qty if item.physical_qty is not None else 0
                        ),
                    }
                    for item in paginated["items"]
                ],
                "total": paginated["total"],
            }
        ),
        200,
    )


def adjust_stock():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data = request.json
    dist_id = data.get("distributor_id")

    # 🔹 SECURITY CHECK
    if not user.has_distributor(dist_id):
        return jsonify({"message": "Accès non autorisé à ce distributeur"}), 403

    try:
        qty = int(data["quantity"])
        prod_id = data["product_id"]

        adj = StockAdjustment(
            date=datetime.now().date(),
            distributor_id=dist_id,
            product_id=prod_id,
            supervisor_id=uid,
            quantity=qty,
            note=data.get("note", "Ajustement manuel"),
        )
        db.session.add(adj)
        update_stock_incremental(dist_id, prod_id, qty)
        db.session.commit()
        return jsonify({"message": "Ajustement enregistré"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def delete_adjustment(adj_id):
    uid = get_jwt_identity()
    user = User.query.get(uid)
    adj = StockAdjustment.query.get_or_404(adj_id)

    # 🔹 SECURITY CHECK
    if not user.has_distributor(adj.distributor_id):
        return jsonify({"message": "Action non autorisée"}), 403

    try:
        update_stock_incremental(adj.distributor_id, adj.product_id, -adj.quantity)
        db.session.delete(adj)
        db.session.commit()
        return jsonify({"message": "Ajustement supprimé"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def get_history(dist_id, prod_id):
    uid = get_jwt_identity()
    user = User.query.get(uid)

    # 🔹 SECURITY CHECK
    if not user.has_distributor(dist_id):
        return jsonify({"message": "Accès non autorisé"}), 403

    move_type = request.args.get("type")
    vendor_id = request.args.get("vendor_id")
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    query = InventoryHistoryView.query.filter_by(
        distributor_id=dist_id, product_id=prod_id
    )

    if move_type and move_type != "all":
        query = query.filter(InventoryHistoryView.type == move_type)
    if vendor_id and vendor_id != "all":
        query = query.filter(InventoryHistoryView.vendor_id == int(vendor_id))
    if start_date:
        query = query.filter(InventoryHistoryView.created_at >= start_date)
    if end_date:
        query = query.filter(InventoryHistoryView.created_at <= f"{end_date} 23:59:59")

    paginated = paginate(query.order_by(InventoryHistoryView.created_at.desc()))
    return (
        jsonify(
            {
                "data": [
                    {
                        "id": h.ref_id,
                        "date": h.created_at.isoformat(),
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
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data = request.json
    dist_id = data.get("distributor_id")

    # 🔹 SECURITY CHECK
    if not user.has_distributor(dist_id):
        return jsonify({"message": "Action non autorisée"}), 403

    try:
        db.session.execute(
            text("EXEC dbo.sp_refresh_inventory @distributor_id=:d_id"),
            {"d_id": dist_id},
        )
        db.session.commit()
        return jsonify({"message": "Inventaire théorique synchronisé"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def upsert_physical_inventory():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data = request.json
    dist_id = data.get("distributor_id")

    # 🔹 SECURITY CHECK
    if not user.has_distributor(dist_id):
        return jsonify({"message": "Action non autorisée"}), 403

    try:
        physical = PhysicalInventory.query.filter_by(
            distributor_id=dist_id, product_id=data["product_id"]
        ).first()
        if not physical:
            physical = PhysicalInventory(
                distributor_id=dist_id,
                product_id=data["product_id"],
                quantity=data["quantity"],
            )
            db.session.add(physical)
        else:
            physical.quantity = data["quantity"]
        db.session.commit()
        return jsonify({"message": "Inventaire physique enregistré"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
