from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from datetime import datetime
from decimal import Decimal
from app.extensions import db
from app.models import (
    Purchase,
    PurchaseItem,
    User,
    Product,
    PurchaseView,
    ProductCategory,
    ProductType,
)

from app.utils.inventory_sync import update_stock_incremental


def get_purchases():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    query = PurchaseView.query

    # Scoping
    if user.role == "superviseur":
        query = query.filter(PurchaseView.supervisor_id == user_id)

    # Date filters
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    if start_date and start_date != "undefined":
        query = query.filter(
            PurchaseView.date >= datetime.fromisoformat(start_date).date()
        )
    if end_date and end_date != "undefined":
        query = query.filter(
            PurchaseView.date <= datetime.fromisoformat(end_date).date()
        )

    # Search
    search = request.args.get("search")
    if search:
        query = query.filter(
            or_(
                PurchaseView.distributeur_nom.ilike(f"%{search}%"),
                PurchaseView.id.cast(db.String).ilike(f"%{search}%"),
            )
        )

    # Filters
    dist_id = request.args.get("distributeur_id")
    if dist_id and dist_id != "all":
        query = query.filter(PurchaseView.distributor_id == dist_id)

    status = request.args.get("status")
    if status and status != "all":
        query = query.filter(PurchaseView.status == status)

    # Pagination
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    pagination = query.order_by(
        PurchaseView.date.desc(), PurchaseView.id.desc()
    ).paginate(page=page, per_page=page_size)

    # Load real Purchase objects with products
    purchase_ids = [p.id for p in pagination.items]
    purchases = (
        Purchase.query.options(
            joinedload(Purchase.items).joinedload(PurchaseItem.product)
        )
        .filter(Purchase.id.in_(purchase_ids))
        .all()
    )
    purchases_map = {p.id: p for p in purchases}

    results = []
    for p in pagination.items:
        real_purchase = purchases_map.get(p.id)

        product_list = [
            {
                "product_id": item.product_id,
                "designation": item.product.designation,
                "quantity": item.quantity,
                "price_factory": float(
                    item.product.price_factory or 0
                ),  # Added price for popover details
            }
            for item in (real_purchase.items if real_purchase else [])
        ]

        results.append(
            {
                "id": p.id,
                "date": p.date.isoformat() if p.date else None,
                "distributeur_nom": p.distributeur_nom,
                "distributeur_id": p.distributor_id,
                "montant_total": (
                    float(real_purchase.montant_total or 0) if real_purchase else 0
                ),
                "status": p.status,
                "products": product_list,
            }
        )

    return jsonify({"data": results, "total": pagination.total}), 200


def create_purchase():
    user_id = get_jwt_identity()
    data = request.json

    try:
        distributor_id = data["distributeurId"]
        new_purchase = Purchase(
            date=datetime.fromisoformat(data["date"]).date(),
            distributor_id=distributor_id,
            supervisor_id=user_id,
            status=data.get("status", "en_cours"),
        )

        total_amount = Decimal("0.00")
        for item in data.get("products", []):
            qty = int(item["quantity"])
            if qty <= 0:
                continue  # Skip zeros

            prod = Product.query.get_or_404(item["product_id"])
            price = prod.price_factory

            total_amount += Decimal(str(price)) * qty
            new_purchase.items.append(PurchaseItem(product_id=prod.id, quantity=qty))

            # Increment stock immediately if purchase complete
            if new_purchase.status == "complete":
                update_stock_incremental(distributor_id, prod.id, qty)

        new_purchase.montant_total = total_amount

        db.session.add(new_purchase)
        db.session.commit()
        return jsonify({"message": "Achat enregistré", "id": new_purchase.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def update_purchase(purchase_id):
    purchase = Purchase.query.options(
        joinedload(Purchase.items).joinedload(PurchaseItem.product)
    ).get_or_404(purchase_id)
    data = request.json

    try:
        old_status = purchase.status
        new_status = data.get("status", purchase.status)

        # Rollback old stock if purchase was complete
        if old_status == "complete":
            for item in purchase.items:
                update_stock_incremental(
                    purchase.distributor_id, item.product_id, -item.quantity
                )

        # Update basic fields
        purchase.date = (
            datetime.fromisoformat(data["date"]).date()
            if data.get("date")
            else purchase.date
        )
        purchase.status = new_status
        purchase.distributor_id = data.get("distributeurId", purchase.distributor_id)

        total_amount = Decimal("0.00")
        if "products" in data:
            purchase.items.clear()
            for item in data["products"]:
                qty = int(item["quantity"])
                if qty <= 0:
                    continue

                prod = Product.query.get_or_404(item["product_id"])
                price = prod.price_factory
                total_amount += Decimal(str(price)) * qty
                purchase.items.append(PurchaseItem(product_id=prod.id, quantity=qty))

        purchase.montant_total = total_amount
        db.session.flush()

        # Apply stock if now complete
        if new_status == "complete":
            for item in purchase.items:
                update_stock_incremental(
                    purchase.distributor_id, item.product_id, item.quantity
                )

        db.session.commit()
        return jsonify({"message": "Mise à jour réussie"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def delete_purchase(purchase_id):
    purchase = Purchase.query.options(joinedload(Purchase.items)).get_or_404(
        purchase_id
    )

    try:
        # Rollback stock if purchase complete
        if purchase.status == "complete":
            for item in purchase.items:
                update_stock_incremental(
                    purchase.distributor_id, item.product_id, -item.quantity
                )

        db.session.delete(purchase)
        db.session.commit()
        return jsonify({"message": "Supprimé"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def get_purchase_matrix():
    purchase_id = request.args.get("purchase_id", type=int)
    search = request.args.get("search", "")
    cat = request.args.get("category", "all")
    p_type = request.args.get("product_type", "all")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 25, type=int)

    # 1. Base Query
    query = db.session.query(Product)

    # 2. Join with PurchaseItem to allow sorting by existing quantity
    if purchase_id:
        # Left outer join so we don't lose products with 0 qty
        query = query.outerjoin(
            PurchaseItem,
            db.and_(
                PurchaseItem.product_id == Product.id,
                PurchaseItem.purchase_id == purchase_id,
            ),
        )

    # 3. Filters
    query = query.filter(Product.active == True)
    if cat != "all":
        query = query.filter(Product.category_id == cat)
    if p_type != "all":
        query = query.filter(Product.type_id == p_type)
    if search:
        query = query.filter(
            or_(
                Product.designation.ilike(f"%{search}%"),
                Product.code.ilike(f"%{search}%"),
            )
        )

    # 4. Priority Ordering: Items in this purchase come first
    if purchase_id:
        query = query.order_by(
            db.case((PurchaseItem.id != None, 0), else_=1), Product.designation.asc()
        )
    else:
        query = query.order_by(Product.designation.asc())

    pagination = query.paginate(page=page, per_page=page_size)

    # If editing, get current quantities for this specific purchase
    existing_qtys = {}
    if purchase_id:
        items = PurchaseItem.query.filter_by(purchase_id=purchase_id).all()
        existing_qtys = {item.product_id: item.quantity for item in items}

    data = []
    for p in pagination.items:
        data.append(
            {
                "product_id": p.id,
                "code": p.code,
                "designation": p.designation,
                "price_factory": float(p.price_factory or 0),
                "quantity": existing_qtys.get(p.id, 0),
            }
        )

    return jsonify({"data": data, "total": pagination.total}), 200
