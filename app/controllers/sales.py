from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from datetime import datetime, timedelta
from decimal import Decimal
from app.extensions import db
from app.models import Sale, SaleItem, User, Product, SaleView, Vendor
from app.utils.inventory_sync import update_stock_incremental


def get_sales():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    query = SaleView.query

    if user.role == "superviseur":
        query = query.filter(SaleView.supervisor_id == user_id)

    # Date filters
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    if start_date and start_date != "undefined":
        query = query.filter(SaleView.date >= datetime.fromisoformat(start_date).date())

    if end_date and end_date != "undefined":
        query = query.filter(SaleView.date <= datetime.fromisoformat(end_date).date())

    # Search
    search = request.args.get("search")
    if search:
        query = query.filter(
            or_(
                SaleView.distributeur_nom.ilike(f"%{search}%"),
                SaleView.vendeur_nom.ilike(f"%{search}%"),
                SaleView.vendeur_prenom.ilike(f"%{search}%"),
                SaleView.id.cast(db.String).ilike(f"%{search}%"),
            )
        )

    # Filters
    dist_id = request.args.get("distributeur_id")
    if dist_id and dist_id != "all":
        query = query.filter(SaleView.distributor_id == dist_id)

    status = request.args.get("status")
    if status and status != "all":
        query = query.filter(SaleView.status == status)

    # Pagination
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)

    pagination = query.order_by(SaleView.date.desc(), SaleView.id.desc()).paginate(
        page=page, per_page=page_size
    )

    # Load real Sale objects with products in ONE query
    sale_ids = [s.id for s in pagination.items]

    sales = (
        Sale.query.options(joinedload(Sale.items).joinedload(SaleItem.product))
        .filter(Sale.id.in_(sale_ids))
        .all()
    )
    sales_map = {s.id: s for s in sales}

    results = []
    for s in pagination.items:
        real_sale = sales_map.get(s.id)

        product_list = (
            [
                {
                    "product_id": item.product_id,
                    "designation": item.product.designation,
                    "quantity": item.quantity,
                }
                for item in real_sale.items
            ]
            if real_sale
            else []
        )

        results.append(
            {
                "id": s.id,
                "date": s.date.isoformat() if s.date else None,
                "distributeur_nom": s.distributeur_nom,
                "vendeur_nom": s.vendeur_nom,
                "vendeur_prenom": s.vendeur_prenom,
                "vendeur_type": s.vendeur_type,
                "distributeur_id": s.distributor_id,
                "montant_total": s.montant_total,
                "vendeur_id": s.vendor_id,
                "status": s.status,
                "products": product_list,
            }
        )

    return jsonify({"data": results, "total": pagination.total}), 200


def create_sale():
    user_id = get_jwt_identity()
    data = request.json

    try:
        vendor = Vendor.query.get_or_404(data["acteurId"])
        distributor_id = data["distributeurId"]

        new_sale = Sale(
            date=datetime.fromisoformat(data["date"]).date(),
            distributor_id=distributor_id,
            vendor_id=vendor.id,
            supervisor_id=user_id,
            status=data.get("status", "en_cours"),
        )

        totalPrice = Decimal(0.00)

        for item in data.get("products", []):
            qty = int(item["quantity"])
            if qty <= 0:
                return jsonify({"message": "Quantité invalide"}), 400

            prod = Product.query.get_or_404(item["product_id"])

            if vendor.vendor_type == "gros":
                totalPrice += prod.price_gros * qty
            elif vendor.vendor_type == "superette":
                totalPrice += prod.price_superette * qty
            else:
                totalPrice += prod.price_detail * qty

            new_sale.items.append(SaleItem(product_id=prod.id, quantity=qty))

        new_sale.montant_total = totalPrice

        db.session.add(new_sale)
        db.session.flush()

        # Apply stock if completed
        if new_sale.status == "complete":
            for item in new_sale.items:
                update_stock_incremental(
                    distributor_id, item.product_id, -item.quantity
                )

        db.session.commit()
        return jsonify({"message": "Vente enregistrée", "id": new_sale.id}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def update_sale(sale_id):
    sale = Sale.query.options(joinedload(Sale.items)).get_or_404(sale_id)
    data = request.json

    try:
        old_status = sale.status
        new_status = data.get("status", sale.status)

        # Restore stock if sale was complete
        if old_status == "complete":
            for item in sale.items:
                update_stock_incremental(
                    sale.distributor_id, item.product_id, item.quantity
                )

        # Update basic fields
        sale.date = (
            datetime.fromisoformat(data.get("date")).date()
            if data.get("date")
            else sale.date
        )
        sale.status = new_status
        sale.distributor_id = data.get("distributorId", sale.distributor_id)
        sale.vendor_id = data.get("vendorId", sale.vendor_id)

        vendor = Vendor.query.get_or_404(sale.vendor_id)

        # Replace items if products updated
        totalPrice = Decimal("0.00")
        if "products" in data:
            sale.items.clear()

            for item in data["products"]:
                qty = int(item["quantity"])
                if qty <= 0:
                    return jsonify({"message": "Quantité invalide"}), 400

                prod = Product.query.get_or_404(item["product_id"])

                if vendor.vendor_type == "gros":
                    price = prod.price_gros
                elif vendor.vendor_type == "superette":
                    price = prod.price_superette
                else:
                    price = prod.price_detail

                totalPrice += Decimal(price) * qty

                sale.items.append(SaleItem(product_id=prod.id, quantity=qty))

        sale.montant_total = totalPrice

        db.session.flush()

        # Apply stock if sale is now complete
        if new_status == "complete":
            for item in sale.items:
                update_stock_incremental(
                    sale.distributor_id, item.product_id, -item.quantity
                )

        db.session.commit()
        return jsonify({"message": "Mise à jour réussie"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def delete_sale(sale_id):
    sale = Sale.query.options(joinedload(Sale.items)).get_or_404(sale_id)

    try:
        if sale.status == "complete":
            for item in sale.items:
                update_stock_incremental(
                    sale.distributor_id, item.product_id, item.quantity
                )

        db.session.delete(sale)
        db.session.commit()
        return jsonify({"message": "Supprimé"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_
from datetime import datetime, timedelta
from decimal import Decimal
from app.extensions import db
from app.models import Sale, SaleItem, User, Product, SaleView, Vendor
from app.utils.inventory_sync import update_stock_incremental


def get_weekly_sales_matrix():
    """
    Centerpiece of the Excel-like entry.
    Returns a list of products with a 6-day quantity array and status map.
    """
    # 1. Retrieve and Normalize Params
    start_date_str = request.args.get("start_date")
    v_id = request.args.get("vendor_id")
    dist_id = request.args.get("distributor_id")

    if not all([start_date_str, v_id, dist_id]):
        return (
            jsonify({"message": "Paramètres manquants (Vendeur, Distributeur, Date)"}),
            400,
        )

    # Normalization: Always snap the week to the preceding Saturday
    raw_date = datetime.fromisoformat(start_date_str).date()
    weekday = raw_date.weekday()  # Mon=0, Sat=5, Sun=6

    if weekday == 5:  # Saturday
        start_date = raw_date
    elif weekday == 6:  # Sunday
        start_date = raw_date - timedelta(days=1)
    else:  # Mon-Fri
        start_date = raw_date - timedelta(days=weekday + 2)

    week_dates = [start_date + timedelta(days=i) for i in range(6)]  # Sat to Thu
    end_date = week_dates[-1]

    # 2. Product Query with Matrix Filters
    search = request.args.get("search", "")
    cat = request.args.get("category", "all")
    p_type = request.args.get("product_type", "all")
    fmt = request.args.get("format", "all")
    page = request.args.get("page", 1, type=int)

    prod_query = Product.query
    if cat != "all":
        prod_query = prod_query.filter_by(category_id=cat)
    if p_type != "all":
        prod_query = prod_query.filter_by(type_id=p_type)
    if fmt != "all":
        prod_query = prod_query.filter_by(format=fmt)
    if search:
        prod_query = prod_query.filter(
            or_(
                Product.designation.ilike(f"%{search}%"),
                Product.code.ilike(f"%{search}%"),
            )
        )

    # MSSQL pagination requires order_by
    pagination = prod_query.order_by(Product.designation.asc()).paginate(
        page=page, per_page=25
    )

    # 3. Fetch Existing Sales & Statuses for this specific week/vendor
    sales = Sale.query.filter(
        Sale.vendor_id == v_id, Sale.date >= start_date, Sale.date <= end_date
    ).all()

    status_map = {s.date.isoformat(): s.status for s in sales}
    sale_ids = [s.id for s in sales]
    date_map = {s.id: s.date for s in sales}

    # Build item_map: {(product_id, date): quantity}
    item_map = {}
    if sale_ids:
        items = SaleItem.query.filter(SaleItem.sale_id.in_(sale_ids)).all()
        for itm in items:
            itm_date = date_map.get(itm.sale_id)
            item_map[(itm.product_id, itm_date)] = itm.quantity

    # 4. Construct Result Matrix
    data = []
    for p in pagination.items:
        # Construct the 6-day array for this product
        day_values = [item_map.get((p.id, d), 0) for d in week_dates]

        data.append(
            {
                "product_id": p.id,
                "designation": p.designation,
                "code": p.code,
                "active": p.active,
                "days": day_values,
            }
        )

    return (
        jsonify(
            {
                "data": data,
                "total": pagination.total,
                "dates": [d.isoformat() for d in week_dates],
                "statuses": status_map,
            }
        ),
        200,
    )


def upsert_sale_item():
    """
    Handles 'Save on Blur'. Updates or creates a sale record for a specific cell.
    """
    uid = get_jwt_identity()
    data = request.json

    v_id = data["vendor_id"]
    d_id = data["distributor_id"]
    p_id = data["product_id"]
    target_date = data["date"]
    qty = int(data["quantity"])

    try:
        # 1. Get or Create the Sale Header
        sale = Sale.query.filter_by(vendor_id=v_id, date=target_date).first()
        if not sale:
            sale = Sale(
                date=target_date,
                distributor_id=d_id,
                vendor_id=v_id,
                supervisor_id=uid,
                status="complete",  # Matrix entries default to validated
            )
            db.session.add(sale)
            db.session.flush()  # Get sale.id

        # 2. Get or Create the Sale Item
        item = SaleItem.query.filter_by(sale_id=sale.id, product_id=p_id).first()
        old_qty = item.quantity if item else 0

        if qty <= 0 and item:
            db.session.delete(item)
        elif qty > 0:
            if not item:
                item = SaleItem(sale_id=sale.id, product_id=p_id, quantity=qty)
                db.session.add(item)
            else:
                item.quantity = qty

        # 3. Inventory Reconciliation (Only if sale is complete)
        if sale.status == "complete":
            # Delta logic: if old=5, new=10, we subtract 5 more. if old=10, new=2, we add back 8.
            delta = old_qty - qty
            update_stock_incremental(d_id, p_id, delta)

        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def update_sale_status_by_date():
    uid = get_jwt_identity()
    data = request.json

    v_id = data.get("vendor_id")
    target_date = data.get("date")
    new_status = data.get("status")
    d_id = data.get("distributor_id")

    try:
        sale = Sale.query.filter_by(vendor_id=v_id, date=target_date).first()

        if not sale:
            # If status toggled on a day with no data, just create an empty record
            sale = Sale(
                date=target_date,
                distributor_id=d_id,
                vendor_id=v_id,
                supervisor_id=uid,
                status=new_status,
            )
            db.session.add(sale)
        else:
            old_status = sale.status
            if old_status == new_status:
                return jsonify({"message": "Aucun changement"}), 200

            # --- Critical Inventory Logic ---
            # 1. Moving TO 'complete': Subtract all quantities from stock
            if old_status != "complete" and new_status == "complete":
                for itm in sale.items:
                    update_stock_incremental(
                        sale.distributor_id, itm.product_id, -itm.quantity
                    )

            # 2. Moving FROM 'complete': Add back all quantities to stock
            elif old_status == "complete" and new_status != "complete":
                for itm in sale.items:
                    update_stock_incremental(
                        sale.distributor_id, itm.product_id, itm.quantity
                    )

            sale.status = new_status

        db.session.commit()
        return jsonify({"message": "Statut mis à jour"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
