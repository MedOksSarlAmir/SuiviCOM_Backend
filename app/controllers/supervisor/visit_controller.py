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
        return jsonify({"message": "Date required"}), 400

    # 🔹 Supervisor scoping
    if user and user.role == "superviseur":
        assigned = [d.id for d in Distributor.query.filter_by(supervisor_id=uid).all()]
        if not assigned:
            return jsonify({"data": [], "message": "Aucun distributeur assigné"}), 200
        if not dist_id:
            dist_id = assigned[0]
        if dist_id not in assigned:
            return jsonify({"message": "Accès non autorisé"}), 403

    search = request.args.get("search", "")
    v_type = request.args.get("vendor_type", "all")

    # 🔹 Base query with OUTER JOIN to visits on the selected date
    vendor_query = (
        db.session.query(Vendor)
        .outerjoin(Visit, and_(Visit.vendor_id == Vendor.id, Visit.date == target_date))
        .filter(Vendor.distributor_id == dist_id)
    )

    # 🔹 Search filter
    if search:
        vendor_query = vendor_query.filter(
            or_(
                Vendor.last_name.ilike(f"%{search}%"),
                Vendor.first_name.ilike(f"%{search}%"),
                Vendor.code.ilike(f"%{search}%"),
            )
        )

    # 🔹 Vendor type filter
    if v_type != "all":
        vendor_query = vendor_query.filter(Vendor.vendor_type == v_type)

    # 🔹 IMPORTANT CONDITION
    # Show vendor if ACTIVE or has a visit row for that date
    vendor_query = vendor_query.filter(or_(Vendor.active == True, Visit.id.isnot(None)))

    # Remove duplicates caused by join
    vendor_query = vendor_query.distinct()

    # Pagination (still accurate now)
    paginated = paginate(vendor_query.order_by(Vendor.last_name.asc()))

    vendors = paginated["items"]
    vendor_ids = [v.id for v in vendors]

    # 🔹 Fetch visit rows separately for mapping (only for visible vendors)
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

    # 🔹 RESTORED PERMISSION CHECK
    if user.role == "superviseur":
        if vendor.supervisor_id != int(uid):
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
            supervisor_id=uid,
            planned_visits=0,
            actual_visits=0,
            invoice_count=0,
        )
        db.session.add(visit)

    # 🔹 SUPPORT BOTH FRONTEND NAMING CONVENTIONS
    if field in ["planned", "prog"]:
        visit.planned_visits = val
    elif field in ["actual", "done"]:
        visit.actual_visits = val
    elif field in ["invoices", "nb_factures"]:
        visit.invoice_count = val

    db.session.commit()
    return jsonify({"success": True, "visit_id": visit.id}), 200
