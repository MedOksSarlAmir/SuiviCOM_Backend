from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.models import (
    Inventory,
    InventoryHistoryView,
    Distributor,
    User,
    Product,
    ProductCategory,
    StockAdjustment,
)
from app.extensions import db
from sqlalchemy import or_, text
from datetime import datetime
from app.utils.inventory_sync import update_stock_incremental


# ===============================
# GET CURRENT INVENTORY
# ===============================
def get_inventory(dist_id):
    uid = get_jwt_identity()
    user = User.query.get(uid)

    search = request.args.get("search", "")

    # 🔹 DATA SCOPING (not RBAC)
    if user and user.role == "superviseur":
        assigned_ids = [
            d.id for d in Distributor.query.filter_by(supervisor_id=uid).all()
        ]
        if not assigned_ids:
            return jsonify({"data": [], "message": "Aucun distributeur assigné"}), 200

        if not dist_id or dist_id not in assigned_ids:
            dist_id = assigned_ids[0]  # default to first allowed distributor

    if not dist_id:
        return jsonify({"data": [], "message": "Aucun distributeur sélectionné"}), 200

    # Join with Product and Category to allow searching and display
    query = db.session.query(Inventory).join(Product).join(ProductCategory)

    query = query.filter(Inventory.distributor_id == dist_id)

    if search:
        query = query.filter(
            or_(
                Product.designation.ilike(f"%{search}%"),
                Product.code.ilike(f"%{search}%"),
            )
        )

    query = query.order_by(Product.designation.asc())

    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    pagination = query.paginate(page=page, per_page=page_size)

    return (
        jsonify(
            {
                "data": [
                    {
                        "product_id": i.product_id,
                        "code": i.product.code,
                        "designation": i.product.designation,
                        "category": (
                            i.product.category.name if i.product.category else "N/A"
                        ),
                        "stock": i.stock_qte,
                        "last_updated": (
                            i.last_updated.isoformat() if i.last_updated else None
                        ),
                    }
                    for i in pagination.items
                ],
                "total": pagination.total,
                "current_distributor": dist_id,
            }
        ),
        200,
    )


# ===============================
# CREATE STOCK ADJUSTMENT
# ===============================
def create_adjustment(prod_id):
    uid = get_jwt_identity()
    data = request.json

    try:
        # ✅ Validate product exists
        product = Product.query.get(prod_id)
        if not product:
            return jsonify({"message": "Produit introuvable"}), 404

        distributor = Distributor.query.get(data["distributor_id"])
        if not distributor:
            return jsonify({"message": "Distributeur introvable"})

        # ✅ Validate note
        if not data.get("note") or len(data["note"]) < 5:
            return (
                jsonify(
                    {"message": "Une note explicative est obligatoire (5 car. min)"}
                ),
                400,
            )

        qty = int(data.get("quantity", 0))
        if qty == 0:
            return jsonify({"message": "Quantité invalide"}), 400

        # ✅ Create adjustment record
        new_adj = StockAdjustment(
            date=datetime.fromisoformat(data["date"]).date(),
            distributor_id=data["distributor_id"],
            product_id=prod_id,
            quantity=qty,
            note=data["note"],
            supervisor_id=uid,
        )

        db.session.add(new_adj)

        # ✅ Apply stock movement
        update_stock_incremental(data["distributor_id"], prod_id, qty)

        db.session.commit()
        return jsonify({"message": "Ajustement enregistré"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


# ===============================
# DELETE STOCK ADJUSTMENT
# ===============================
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


# ===============================
# FORCE INVENTORY REBUILD (SP)
# ===============================
def refresh_inventory_data():
    try:
        db.session.execute(text("EXEC dbo.sp_refresh_inventory"))
        db.session.commit()
        return jsonify({"message": "Stock recalculé avec succès"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


# ===============================
# INVENTORY PRODUCT HISTORY
# ===============================
def get_product_history(dist_id, prod_id):
    query = InventoryHistoryView.query.filter_by(
        distributor_id=dist_id, product_id=prod_id
    ).order_by(InventoryHistoryView.date.desc(), InventoryHistoryView.ref_id.desc())

    page = request.args.get("page", 1, type=int)

    per_page = request.args.get("pageSize", 10, type=int)
    pagination = query.paginate(page=page, per_page=per_page)

    return (
        jsonify(
            {
                "data": [
                    {
                        "id": h.ref_id,
                        "date": h.date.isoformat() if h.date else None,
                        "type": h.type,
                        "qte": h.qte,
                        "actor": h.actor_name,
                        "note": h.note,
                    }
                    for h in pagination.items
                ],
                "total": pagination.total,
            }
        ),
        200,
    )
