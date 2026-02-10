from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import case, or_, and_
from sqlalchemy.orm import joinedload
from decimal import Decimal
from datetime import datetime
from app.extensions import db
from app.models import Purchase, PurchaseItem, PurchaseView, Product, User
from app.utils.stock_ops import update_stock_incremental
from app.utils.pagination import paginate


def list_purchases():
    uid = get_jwt_identity()
    user = User.query.get_or_404(uid)

    # 1. Start with the View for efficient filtering
    query = PurchaseView.query
    if user.role == "superviseur":
        query = query.filter(PurchaseView.supervisor_id == uid)

    # Date filters
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    if start_date:
        query = query.filter(PurchaseView.date >= datetime.fromisoformat(start_date).date())
    if end_date:
        query = query.filter(PurchaseView.date <= datetime.fromisoformat(end_date).date())

    # 2. Paginate the view results
    paginated = paginate(query.order_by(PurchaseView.date.desc()))
    
    # 3. Get the IDs of the purchases on the current page
    purchase_ids = [p.id for p in paginated["items"]]

    # 4. Fetch the actual Purchase objects with their items and product details in ONE query
    # We use joinedload to avoid "N+1" query problems (fetching items one by one)
    actual_purchases = (
        Purchase.query
        .options(joinedload(Purchase.items).joinedload(PurchaseItem.product))
        .filter(Purchase.id.in_(purchase_ids))
        .all()
    )
    
    # Create a map { id: purchase_object } for easy retrieval
    purchase_map = {p.id: p for p in actual_purchases}

    # 5. Build the final response
    results = []
    for p_view in paginated["items"]:
        # Get the full object from our map
        full_purchase = purchase_map.get(p_view.id)
        
        # Format the product list for the frontend popover
        product_list = []
        if full_purchase:
            for item in full_purchase.items:
                product_list.append({
                    "product_id": item.product_id,
                    "name": item.product.name, # Backend 'name' is 'designation'
                    "quantity": item.quantity,
                    "price_factory": float(item.product.price_factory or 0)
                })

        results.append({
            "id": p_view.id,
            "date": p_view.date.isoformat(),
            "distributor_name": p_view.distributor_name,
            "distributor_id": p_view.distributor_id,
            "total_amount": float(p_view.total_amount or 0),
            "status": p_view.status,
            "products": product_list # <--- This is your list for the hover/popover
        })

    return jsonify({"data": results, "total": paginated["total"]}), 200

def create_purchase():
    uid = get_jwt_identity()
    data = request.json

    dist_id = data["distributor_id"]
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
    return jsonify({"message": "Purchase recorded", "id": new_purchase.id}), 201



def update_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    data = request.json
    try:
        old_status = purchase.status
        new_status = data.get("status", purchase.status)

        if old_status == "complete":
            for item in purchase.items:
                update_stock_incremental(purchase.distributor_id, item.product_id, -item.quantity)

        purchase.status = new_status
        if "products" in data:
            purchase.items.clear()
            total = 0
            for item in data["products"]:
                prod = Product.query.get(item["product_id"])
                total += prod.price_factory * item["quantity"]
                purchase.items.append(PurchaseItem(product_id=prod.id, quantity=item["quantity"]))
            purchase.total_amount = total

        if new_status == "complete":
            for item in purchase.items:
                update_stock_incremental(purchase.distributor_id, item.product_id, item.quantity)

        db.session.commit()
        return jsonify({"message": "Purchase updated"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
    
    
def delete_purchase(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    try:
        # Rollback stock if it was completed
        if purchase.status == "complete":
            for item in purchase.items:
                update_stock_incremental(purchase.distributor_id, item.product_id, -item.quantity)
        
        db.session.delete(purchase)
        db.session.commit()
        return jsonify({"message": "Purchase deleted"}), 200
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
            and_(
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
                Product.name.ilike(f"%{search}%"),
                Product.code.ilike(f"%{search}%"),
            )
        )

    # 4. Priority Ordering: Items in this purchase come first
    if purchase_id:
        query = query.order_by(
            case((PurchaseItem.id != None, 0), else_=1), Product.name.asc()
        )
    else:
        query = query.order_by(Product.name.asc())

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
                "name": p.name,
                "price_factory": float(p.price_factory or 0),
                "quantity": existing_qtys.get(p.id, 0),
            }
        )
    
    return jsonify({"data": data, "total": pagination.total}), 200