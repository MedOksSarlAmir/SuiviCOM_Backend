from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from datetime import datetime
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
                update_stock_incremental(sale.distributor_id, item.product_id, item.quantity)

        # Update basic fields
        sale.date = (
            datetime.fromisoformat(data.get("date")).date() if data.get("date") else sale.date
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
                update_stock_incremental(sale.distributor_id, item.product_id, -item.quantity)

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
