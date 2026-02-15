from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import and_, or_
from app.extensions import db
from app.models import Visit, Vendor, User, Distributor
from app.utils.pagination import paginate


def get_visit_matrix():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    dist_id = request.args.get("distributor_id", type=int)
    target_date = request.args.get("date")

    if not target_date:
        return jsonify({"message": "Date requise"}), 400

    # 🔹 SCOPING: Get assigned distributors from the junction table
    if user and user.role == "superviseur":
        assigned_ids = [d.id for d in user.supervised_distributors]

        if not assigned_ids:
            return jsonify({"data": [], "message": "Aucun distributeur assigné"}), 200

        # Default to the first assigned distributor if none specified
        if not dist_id:
            dist_id = assigned_ids[0]

        # 🔹 SECURITY: Ensure requested distributor is in the supervisor's list
        if dist_id not in assigned_ids:
            return jsonify({"message": "Accès non autorisé à ce distributeur"}), 403

    search = request.args.get("search", "")
    v_type = request.args.get("vendor_type", "all")

    # Base query: Join vendors with their visit data for the specific date
    vendor_query = (
        db.session.query(Vendor)
        .outerjoin(Visit, and_(Visit.vendor_id == Vendor.id, Visit.date == target_date))
        .filter(Vendor.distributor_id == dist_id)
    )

    if search:
        vendor_query = vendor_query.filter(
            or_(
                Vendor.last_name.ilike(f"%{search}%"),
                Vendor.first_name.ilike(f"%{search}%"),
                Vendor.code.ilike(f"%{search}%"),
            )
        )

    if v_type != "all":
        vendor_query = vendor_query.filter(Vendor.vendor_type == v_type)

    # Show vendor if ACTIVE or if they already have data for this date
    vendor_query = vendor_query.filter(or_(Vendor.active == True, Visit.id.isnot(None)))
    vendor_query = vendor_query.distinct()

    paginated = paginate(vendor_query.order_by(Vendor.last_name.asc()))

    vendors = paginated["items"]
    vendor_ids = [v.id for v in vendors]

    # Fetch visit rows for the vendors in the current page
    visits = Visit.query.filter(
        and_(Visit.date == target_date, Visit.vendor_id.in_(vendor_ids))
    ).all()
    visit_map = {v.vendor_id: v for v in visits}

    data = []
    for v in vendors:
        visit = visit_map.get(v.id)
        data.append(
            {
                "vendor_id": v.id,
                "vendor_name": f"{v.first_name} {v.last_name}",
                "vendor_code": v.code,
                "vendor_type": v.vendor_type,
                "planned": visit.planned_visits if visit else 0,
                "actual": visit.actual_visits if visit else 0,
                "invoices": visit.invoice_count if visit else 0,
                "visit_id": visit.id if visit else None,
                "active": v.active,
            }
        )

    return (
        jsonify(
            {"data": data, "total": paginated["total"], "current_distributor": dist_id}
        ),
        200,
    )


def upsert_visit():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data = request.json

    vendor = Vendor.query.get_or_404(data["vendor_id"])

    # 🔹 SECURITY CHECK: Access to vendor's distributor via junction table helper
    if user.role == "superviseur" and not user.has_distributor(vendor.distributor_id):
        return jsonify({"message": "Action non autorisée"}), 403

    target_date = data["date"]
    field = data["field"]
    val = int(data.get("value", 0))

    visit = Visit.query.filter_by(vendor_id=vendor.id, date=target_date).first()

    if not visit:
        visit = Visit(
            date=target_date,
            vendor_id=vendor.id,
            distributor_id=vendor.distributor_id,
            supervisor_id=uid,  # Log who created the record
            planned_visits=0,
            actual_visits=0,
            invoice_count=0,
        )
        db.session.add(visit)

    # Support multiple frontend field naming conventions
    if field in ["planned", "prog"]:
        visit.planned_visits = val
    elif field in ["actual", "done"]:
        visit.actual_visits = val
    elif field in ["invoices", "nb_factures"]:
        visit.invoice_count = val

    db.session.commit()
    return jsonify({"success": True, "visit_id": visit.id}), 200


def bulk_upsert_visits():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    changes = request.json

    if not isinstance(changes, list):
        return jsonify({"message": "Format invalide, liste attendue"}), 400

    processed_count = 0
    try:
        # Group changes by vendor/date to minimize database lookups
        grouped = {}
        for item in changes:
            key = (item["vendor_id"], item["date"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(item)

        for (v_id, target_date), items in grouped.items():
            vendor = Vendor.query.get(v_id)
            if not vendor:
                continue

            # 🔹 SECURITY CHECK: Verify access to vendor's distributor
            if user.role == "superviseur" and not user.has_distributor(
                vendor.distributor_id
            ):
                continue

            visit = Visit.query.filter_by(vendor_id=v_id, date=target_date).first()
            if not visit:
                visit = Visit(
                    date=target_date,
                    vendor_id=v_id,
                    distributor_id=vendor.distributor_id,
                    supervisor_id=uid,
                    planned_visits=0,
                    actual_visits=0,
                    invoice_count=0,
                )
                db.session.add(visit)

            for item in items:
                field = item["field"]
                val = int(item.get("value", 0))

                if field in ["planned", "prog"]:
                    visit.planned_visits = val
                elif field in ["actual", "done"]:
                    visit.actual_visits = val
                elif field in ["invoices", "nb_factures"]:
                    visit.invoice_count = val

            processed_count += 1

        db.session.commit()
        return jsonify({"success": True, "processed": processed_count}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500
