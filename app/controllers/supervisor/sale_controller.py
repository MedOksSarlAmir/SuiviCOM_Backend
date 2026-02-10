from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_, case
from datetime import datetime, timedelta
from decimal import Decimal
from app.extensions import db
from app.models import Sale, SaleItem, User, Product, SaleView, Vendor
from app.utils.stock_ops import update_stock_incremental
from app.utils.pagination import paginate


def list_sales():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    query = SaleView.query

    # Role Scoping
    if user.role == "superviseur":
        query = query.filter(SaleView.supervisor_id == user_id)
    elif user.role in ["chef_zone", "regional"]:
        # Future: Filter by User hierarchy IDs
        pass

    # Date filters
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    if start_date:
        query = query.filter(SaleView.date >= datetime.fromisoformat(start_date).date())
    if end_date:
        query = query.filter(SaleView.date <= datetime.fromisoformat(end_date).date())

    # Search & Sorting
    search = request.args.get("search")
    if search:
        query = query.filter(
            or_(
                SaleView.distributor_name.ilike(f"%{search}%"),
                SaleView.vendor_last_name.ilike(f"%{search}%"),
                SaleView.id.cast(db.String).ilike(f"%{search}%"),
            )
        )

    paginated = paginate(query.order_by(SaleView.date.desc(), SaleView.id.desc()))

    # Build results from View (very fast)
    results = []
    for s in paginated["items"]:
        results.append(
            {
                "id": s.id,
                "date": s.date.isoformat() if s.date else None,
                "distributor_name": s.distributor_name,
                "vendor_name": f"{s.vendor_first_name} {s.vendor_last_name}",
                "vendor_type": s.vendor_type,
                "total_amount": float(s.total_amount or 0),
                "status": s.status,
            }
        )

    return jsonify({"data": results, "total": paginated["total"]}), 200


def upsert_sale_item():
    """Save on Blur logic"""
    uid = get_jwt_identity()
    data = request.json

    v_id = data.get("vendor_id")
    p_id = data.get("product_id")
    target_date = data.get("date")
    qty = int(data.get("quantity", 0))

    vendor = Vendor.query.get_or_404(v_id)

    try:
        sale = Sale.query.filter_by(vendor_id=v_id, date=target_date).first()
        if not sale:
            sale = Sale(
                date=target_date,
                distributor_id=vendor.distributor_id,
                vendor_id=v_id,
                supervisor_id=uid,
                status="complete",  # Default to complete for matrix entries
                total_amount=0,
            )
            db.session.add(sale)
            db.session.flush()

        item = SaleItem.query.filter_by(sale_id=sale.id, product_id=p_id).first()
        old_qty = item.quantity if item else 0

        if qty <= 0:
            if item:
                db.session.delete(item)
        else:
            if not item:
                item = SaleItem(sale_id=sale.id, product_id=p_id, quantity=qty)
                db.session.add(item)
            else:
                item.quantity = qty

        # Sync stock if sale is complete
        if sale.status == "complete":
            delta = (
                old_qty - qty
            )  # If old was 10 and new is 12, delta is -2 (subtract more)
            update_stock_incremental(vendor.distributor_id, p_id, delta)

        db.session.flush()
        _recalculate_total(sale)
        db.session.commit()

        return jsonify({"success": True, "new_total": float(sale.total_amount)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def _recalculate_total(sale):
    """Internal helper to refresh total amount based on vendor type pricing"""
    total = Decimal("0.00")
    v_type = sale.vendor.vendor_type

    for item in sale.items:
        p = item.product
        if v_type == "gros":
            price = p.price_wholesale
        elif v_type == "superette":
            price = p.price_supermarket
        else:
            price = p.price_retail

        total += Decimal(str(price or 0)) * item.quantity

    sale.total_amount = total



def get_weekly_matrix():
    start_date_str = request.args.get("start_date")
    vendor_id = request.args.get("vendor_id")

    search = request.args.get("search", "")
    cat = request.args.get("category", "all")
    p_type = request.args.get("product_type", "all")
    fmt = request.args.get("format", "all")

    if not start_date_str or not vendor_id:
        return jsonify({"message": "Vendor and Date required"}), 400

    vendor = Vendor.query.get_or_404(int(vendor_id))

    raw_date = datetime.fromisoformat(start_date_str).date()
    weekday = raw_date.weekday()

    if weekday == 5:
        start_date = raw_date
    elif weekday == 6:
        start_date = raw_date - timedelta(days=1)
    else:
        start_date = raw_date - timedelta(days=weekday + 2)

    week_dates = [start_date + timedelta(days=i) for i in range(6)]
    end_date = week_dates[-1]

    sales = Sale.query.filter(
        Sale.vendor_id == vendor.id,
        Sale.date >= start_date,
        Sale.date <= end_date
    ).all()

    sale_ids = [s.id for s in sales]
    status_map = {s.date.isoformat(): s.status for s in sales}

    involved_product_ids = []
    if sale_ids:
        involved_product_ids = [
            p[0] for p in db.session.query(SaleItem.product_id)
            .filter(SaleItem.sale_id.in_(sale_ids))
            .distinct()
            .all()
        ]

    # ---------- PRODUCT QUERY ----------
    base_query = Product.query.filter(Product.active == True)

    if cat != "all":
        base_query = base_query.filter(Product.category_id == int(cat))
    if p_type != "all":
        base_query = base_query.filter(Product.type_id == int(p_type))
    if fmt != "all":
        base_query = base_query.filter(Product.format == fmt)
    if search:
        like = f"%{search}%"
        base_query = base_query.filter(or_(Product.name.ilike(like), Product.code.ilike(like)))

    # ✅ COUNT WITHOUT ORDER BY (IMPORTANT FOR SQL SERVER)
    total = base_query.order_by(None).count()

    # ---------- ORDERING ----------
    if involved_product_ids:
        ordered_query = base_query.order_by(
            case((Product.id.in_(involved_product_ids), 0), else_=1),
            Product.name.asc()
        )
    else:
        ordered_query = base_query.order_by(Product.name.asc())

    # ---------- PAGINATION ----------
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("pageSize", 25))

    items = ordered_query.offset((page - 1) * page_size).limit(page_size).all()

    # ---------- MAP QUANTITIES ----------
    item_map = {}
    if sale_ids:
        sale_items = SaleItem.query.filter(SaleItem.sale_id.in_(sale_ids)).all()
        sale_date_by_id = {s.id: s.date for s in sales}
        for itm in sale_items:
            sale_date = sale_date_by_id.get(itm.sale_id)
            if sale_date:
                item_map[(itm.product_id, sale_date)] = itm.quantity

    data = []
    for p in items:
        if vendor.vendor_type == "gros":
            price = p.price_wholesale
        elif vendor.vendor_type == "superette":
            price = p.price_supermarket
        else:
            price = p.price_retail

        data.append({
            "active": p.active,
            "product_id": p.id,
            "name": p.name,
            "code": p.code,
            "unit_price": float(price or 0),
            "days": [item_map.get((p.id, d), 0) for d in week_dates],
        })

    return jsonify({
        "data": data,
        "total": total,
        "dates": [d.isoformat() for d in week_dates],
        "statuses": status_map,
    }), 200


def update_sale_status_by_date():
    uid = get_jwt_identity()
    data = request.json
    v_id = data.get("vendor_id")
    target_date = data.get("date")
    new_status = data.get("status")
    
    vendor = Vendor.query.get_or_404(v_id)

    try:
        sale = Sale.query.filter_by(vendor_id=v_id, date=target_date).first()
        if not sale:
            sale = Sale(date=target_date, distributor_id=vendor.distributor_id, vendor_id=v_id, supervisor_id=uid, status=new_status)
            db.session.add(sale)
        else:
            old_status = sale.status
            if old_status == new_status: return jsonify({"message": "Aucun changement"}), 200

            # Stock Sync logic
            if old_status != "complete" and new_status == "complete":
                for itm in sale.items:
                    update_stock_incremental(sale.distributor_id, itm.product_id, -itm.quantity)
            elif old_status == "complete" and new_status != "complete":
                for itm in sale.items:
                    update_stock_incremental(sale.distributor_id, itm.product_id, itm.quantity)
            sale.status = new_status

        db.session.commit()
        return jsonify({"message": "Statut mis à jour"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500