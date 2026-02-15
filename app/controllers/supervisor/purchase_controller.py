from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import case, or_, and_
from sqlalchemy.orm import joinedload
from decimal import Decimal
from datetime import datetime
from app.extensions import db
from app.models import Purchase, PurchaseItem, PurchaseView, Product, User, Distributor
from app.utils.stock_ops import update_stock_incremental
from app.utils.pagination import paginate


def list_purchases():
    uid = get_jwt_identity()
    user = User.query.get_or_404(uid)
    query = PurchaseView.query

    # 🔹 SCOPING: Use the junction table
    if user.role == "superviseur":
        dist_ids = [d.id for d in user.supervised_distributors]
        query = query.filter(PurchaseView.distributor_id.in_(dist_ids))

    search = request.args.get("search")
    if search:
        query = query.filter(PurchaseView.id.ilike(f"%{search}%"))

    distributor_id = request.args.get("distributor_id")
    if distributor_id and distributor_id != "all":
        query = query.filter(PurchaseView.distributor_id == distributor_id)

    paginated = paginate(query.order_by(PurchaseView.date.desc()))
    purchase_ids = [p.id for p in paginated["items"]]
    actual_purchases = (
        Purchase.query.options(
            joinedload(Purchase.items).joinedload(PurchaseItem.product)
        )
        .filter(Purchase.id.in_(purchase_ids))
        .all()
    )
    purchase_map = {p.id: p for p in actual_purchases}

    results = []
    for p_view in paginated["items"]:
        full_purchase = purchase_map.get(p_view.id)
        product_list = []
        if full_purchase:
            for item in full_purchase.items:
                product_list.append(
                    {
                        "product_id": item.product_id,
                        "name": item.product.name,
                        "quantity": item.quantity,
                        "price_factory": float(item.product.price_factory or 0),
                    }
                )
        results.append(
            {
                "id": p_view.id,
                "date": p_view.date.isoformat(),
                "distributor_name": p_view.distributor_name,
                "distributor_id": p_view.distributor_id,
                "total_amount": float(p_view.total_amount or 0),
                "status": p_view.status,
                "products": product_list,
            }
        )

    return jsonify({"data": results, "total": paginated["total"]}), 200


def create_purchase():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data = request.json
    dist_id = data["distributor_id"]

    # 🔹 SECURITY CHECK
    if not user.has_distributor(dist_id):
        return jsonify({"message": "Accès non autorisé à ce distributeur"}), 403

    new_purchase = Purchase(
        date=datetime.fromisoformat(data["date"]).date(),
        distributor_id=dist_id,
        supervisor_id=uid,
        status=data.get("status", "en_cours"),
    )

    total = Decimal("0.00")
    for item in data.get("products", []):
        qty = int(item["quantity"])
        if qty <= 0:
            continue
        prod = Product.query.get_or_404(item["product_id"])
        total += prod.price_factory * qty
        new_purchase.items.append(PurchaseItem(product_id=prod.id, quantity=qty))
        if new_purchase.status == "complete":
            update_stock_incremental(dist_id, prod.id, qty)

    new_purchase.total_amount = total
    db.session.add(new_purchase)
    db.session.commit()
    return jsonify({"message": "Achat enregistré", "id": new_purchase.id}), 201


def update_purchase(purchase_id):
    uid = get_jwt_identity()
    user = User.query.get(uid)
    purchase = Purchase.query.get_or_404(purchase_id)
    data = request.json

    # 🔹 SECURITY CHECK
    if not user.has_distributor(purchase.distributor_id):
        return jsonify({"message": "Action non autorisée"}), 403

    try:
        old_status = purchase.status
        new_status = data.get("status", purchase.status)
        if old_status == "complete":
            for item in purchase.items:
                update_stock_incremental(
                    purchase.distributor_id, item.product_id, -item.quantity
                )

        purchase.status = new_status
        if "products" in data:
            purchase.items.clear()
            total = 0
            for item in data["products"]:
                prod = Product.query.get(item["product_id"])
                total += prod.price_factory * item["quantity"]
                purchase.items.append(
                    PurchaseItem(product_id=prod.id, quantity=item["quantity"])
                )
            purchase.total_amount = total

        if new_status == "complete":
            for item in purchase.items:
                update_stock_incremental(
                    purchase.distributor_id, item.product_id, item.quantity
                )

        db.session.commit()
        return jsonify({"message": "Achat mis à jour"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def get_purchase_matrix():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    purchase_id = request.args.get("purchase_id", type=int)
    search = request.args.get("search", "")
    cat = request.args.get("category", "all")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 25, type=int)

    if purchase_id:
        p = Purchase.query.get(purchase_id)
        if p and not user.has_distributor(p.distributor_id):
            return jsonify({"message": "Action non autorisée"}), 403

    query = db.session.query(Product).filter(Product.active == True)
    if purchase_id:
        query = query.outerjoin(
            PurchaseItem,
            and_(
                PurchaseItem.product_id == Product.id,
                PurchaseItem.purchase_id == purchase_id,
            ),
        )

    if cat != "all":
        query = query.filter(Product.category_id == cat)
    if search:
        query = query.filter(
            or_(Product.name.ilike(f"%{search}%"), Product.code.ilike(f"%{search}%"))
        )

    if purchase_id:
        query = query.order_by(
            case((PurchaseItem.id != None, 0), else_=1), Product.name.asc()
        )
    else:
        query = query.order_by(Product.name.asc())

    pagination = query.paginate(page=page, per_page=page_size)
    existing_qtys = {}
    if purchase_id:
        items = PurchaseItem.query.filter_by(purchase_id=purchase_id).all()
        existing_qtys = {item.product_id: item.quantity for item in items}

    data = [
        {
            "product_id": p.id,
            "code": p.code,
            "name": p.name,
            "price_factory": float(p.price_factory or 0),
            "quantity": existing_qtys.get(p.id, 0),
        }
        for p in pagination.items
    ]

    return jsonify({"data": data, "total": pagination.total}), 200
