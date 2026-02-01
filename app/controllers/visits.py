from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import or_, and_
from datetime import datetime
from app.extensions import db
from app.models import Visit, VisitView, User, Vendor

def get_visits():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    query = VisitView.query

    # Scoping: Supervisors only see their own assignments
    if user.role == "superviseur":
        query = query.filter(VisitView.supervisor_id == user_id)

    # Date filters
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    if start_date and start_date != "undefined":
        query = query.filter(
            VisitView.date >= datetime.fromisoformat(start_date).date()
        )
    if end_date and end_date != "undefined":
        query = query.filter(VisitView.date <= datetime.fromisoformat(end_date).date())

    # Search: By Vendor Name or Visit ID
    search = request.args.get("search")
    if search:
        query = query.filter(
            or_(
                VisitView.vendeur_nom.ilike(f"%{search}%"),
                VisitView.vendeur_prenom.ilike(f"%{search}%"),
                VisitView.id.cast(db.String).ilike(f"%{search}%"),
            )
        )

    # Filters: Distributor & Status
    dist_id = request.args.get("distributeur_id")
    if dist_id and dist_id != "all":
        query = query.filter(VisitView.distributor_id == dist_id)

    status = request.args.get("status")
    if status and status != "all":
        query = query.filter(VisitView.status == status)

    # Pagination
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 20, type=int)
    pagination = query.order_by(VisitView.date.desc(), VisitView.id.desc()).paginate(
        page=page, per_page=page_size
    )

    results = []
    for v in pagination.items:
        results.append(
            {
                "id": v.id,
                "date": v.date.isoformat() if v.date else None,
                "distributeur_nom": v.distributeur_nom,
                "distributeur_id": v.distributor_id,
                "vendeur_nom": v.vendeur_nom,
                "vendeur_prenom": v.vendeur_prenom,
                "vendeur_id": v.vendor_id,
                "visites_programmees": v.visites_programmees,
                "visites_effectuees": v.visites_effectuees,
                "nb_factures": v.nb_factures,
                "status": v.status,
            }
        )

    return jsonify({"data": results, "total": pagination.total}), 200


def create_visit():
    user_id = get_jwt_identity()
    data = request.json
    try:
        new_visit = Visit(
            date=datetime.fromisoformat(data["date"]).date(),
            distributor_id=data["distributeurId"],
            vendor_id=data["vendeurId"],
            supervisor_id=user_id,
            visites_programmees=data.get("visites_programmees", 0),
            visites_effectuees=data.get("visites_effectuees", 0),
            nb_factures=data.get("nb_factures", 0),
            status=data.get("status", "programmées/non effectuée"),
        )
        db.session.add(new_visit)
        db.session.commit()
        return jsonify({"message": "Visite enregistrée", "id": new_visit.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def update_visit(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    data = request.json
    try:
        visit.date = (
            datetime.fromisoformat(data["date"]).date()
            if "date" in data
            else visit.date
        )
        visit.visites_programmees = data.get(
            "visites_programmees", visit.visites_programmees
        )
        visit.visites_effectuees = data.get(
            "visites_effectuees", visit.visites_effectuees
        )
        visit.nb_factures = data.get("nb_factures", visit.nb_factures)
        visit.status = data.get("status", visit.status)
        visit.vendor_id = data.get("vendeurId", visit.vendor_id)

        db.session.commit()
        return jsonify({"message": "Visite mise à jour"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


def delete_visit(visit_id):
    visit = Visit.query.get_or_404(visit_id)
    try:
        db.session.delete(visit)
        db.session.commit()
        return jsonify({"message": "Visite supprimée"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500



def get_visit_matrix():
    uid = get_jwt_identity()
    dist_id = request.args.get("distributor_id")
    target_date = request.args.get("date") # Expected YYYY-MM-DD
    
    if not dist_id or not target_date:
        return jsonify({"message": "Distributeur et Date requis"}), 400

    # Filters
    search = request.args.get("search", "")
    v_type = request.args.get("vendor_type", "all")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("pageSize", 20, type=int)

    # 1. Get Vendors Query
    vendor_query = Vendor.query.filter_by(distributor_id=dist_id, active=True)
    if search:
        vendor_query = vendor_query.filter(Vendor.nom.ilike(f"%{search}%"))
    if v_type != "all":
        vendor_query = vendor_query.filter_by(vendor_type=v_type)

    pagination = vendor_query.paginate(page=page, per_page=per_page)

    # 2. Get existing Visit data for these vendors on this date
    vendor_ids = [v.id for v in pagination.items]
    existing_visits = Visit.query.filter(
        and_(Visit.date == target_date, Visit.vendor_id.in_(vendor_ids))
    ).all()
    
    visit_map = {v.vendor_id: v for v in existing_visits}

    # 3. Build Matrix
    data = []
    for v in pagination.items:
        visit = visit_map.get(v.id)
        data.append({
            "vendor_id": v.id,
            "vendor_name": f"{v.nom} {v.prenom}",
            "vendor_code": v.code,
            "vendor_type": v.vendor_type,
            "prog": visit.visites_programmees if visit else 0,
            "done": visit.visites_effectuees if visit else 0,
            "invoices": visit.nb_factures if visit else 0,
            "visit_id": visit.id if visit else None
        })

    return jsonify({
        "data": data,
        "total": pagination.total
    }), 200

def upsert_visit():
    uid = get_jwt_identity()
    data = request.json # { vendor_id, date, field, value }
    
    v_id = data.get("vendor_id")
    target_date = data.get("date")
    field = data.get("field") # 'prog', 'done', or 'invoices'
    val = int(data.get("value", 0))

    # Find existing or create
    visit = Visit.query.filter_by(vendor_id=v_id, date=target_date).first()
    
    if not visit:
        # Need distributor_id to create
        vendor = Vendor.query.get(v_id)
        visit = Visit(
            date=target_date,
            vendor_id=v_id,
            distributor_id=vendor.distributor_id,
            supervisor_id=uid,
            status="effectuée" if field == "done" and val > 0 else "programmées/non effectuée"
        )
        db.session.add(visit)

    if field == "prog": visit.visites_programmees = val
    elif field == "done": visit.visites_effectuees = val
    elif field == "invoices": visit.nb_factures = val

    try:
        db.session.commit()
        return jsonify({"success": True, "visit_id": visit.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500