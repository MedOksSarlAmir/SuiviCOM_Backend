from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import or_, and_
from datetime import datetime
from app.extensions import db
from app.models import Visit, VisitView, User, Vendor
from app.models import Distributor


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

    # Filters: Distributor 
    dist_id = request.args.get("distributeur_id")
    if dist_id and dist_id != "all":
        query = query.filter(VisitView.distributor_id == dist_id)

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
    user = User.query.get(uid)
    
    dist_id = request.args.get("distributor_id", type=int)
    target_date = request.args.get("date")
    
    if not target_date:
        return jsonify({"message": "Date requise"}), 400

    # 1. SCOPING: Verify if this supervisor is allowed to see this distributor
    if user and user.role == "superviseur":
        assigned_distributors = Distributor.query.filter_by(supervisor_id=uid).all()
        assigned_ids = [d.id for d in assigned_distributors]
        
        if not assigned_ids:
            return jsonify({"data": [], "total": 0, "message": "Aucun distributeur assigné"}), 200

        if not dist_id:
            dist_id = assigned_ids[0]
        
        if dist_id not in assigned_ids:
            return jsonify({"message": "Accès non autorisé"}), 403

    # 2. FILTERS
    search = request.args.get("search", "")
    v_type = request.args.get("vendor_type", "all")
    page = request.args.get("page", 1, type=int)
    # Increase default pageSize for matrix entry to 50 so "all" usually show
    per_page = request.args.get("pageSize", 50, type=int) 

    # 3. QUERY VENDORS 
    # We filter by distributor_id. 
    # Note: We include active=True because you usually don't report visits for fired/inactive vendors.
    vendor_query = Vendor.query.filter_by(distributor_id=dist_id, active=True)
    
    if search:
        vendor_query = vendor_query.filter(
            or_(Vendor.nom.ilike(f"%{search}%"), Vendor.prenom.ilike(f"%{search}%"), Vendor.code.ilike(f"%{search}%"))
        )
    if v_type != "all":
        vendor_query = vendor_query.filter_by(vendor_type=v_type)

    # MSSQL FIX: Order by name
    vendor_query = vendor_query.order_by(Vendor.nom.asc()) 

    pagination = vendor_query.paginate(page=page, per_page=per_page)

    # 4. Get existing Visit data for these vendors on this date
    vendor_ids = [v.id for v in pagination.items]
    
    existing_visits = Visit.query.filter(
        and_(Visit.date == target_date, Visit.vendor_id.in_(vendor_ids))
    ).all()
    
    visit_map = {v.vendor_id: v for v in existing_visits}

    # 5. Build Result
    data = []
    for v in pagination.items:
        visit = visit_map.get(v.id)
        data.append({
            "vendor_id": v.id,
            "vendor_name": f"{v.nom} {v.prenom}",
            "vendor_code": v.code,
            "vendor_type": v.vendor_type,
            # If no visit record exists yet, the matrix shows 0s ready to be filled
            "prog": visit.visites_programmees if visit else 0,
            "done": visit.visites_effectuees if visit else 0,
            "invoices": visit.nb_factures if visit else 0,
            "visit_id": visit.id if visit else None,
        })

    return jsonify({
        "data": data,
        "total": pagination.total,
        "current_distributor": dist_id
    }), 200



def upsert_visit():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data = request.json # { vendor_id, date, field, value }
    
    v_id = data.get("vendor_id")
    target_date = data.get("date")
    field = data.get("field") # 'prog', 'done', or 'invoices'
    val = int(data.get("value", 0))

    # 1. Fetch Vendor and verify permission
    vendor = Vendor.query.get_or_404(v_id)
    
    if user.role == "superviseur":
        if vendor.supervisor_id != int(uid):
            return jsonify({"message": "Action non autorisée"}), 403

    # 2. Find existing or create
    visit = Visit.query.filter_by(vendor_id=v_id, date=target_date).first()
    
    if not visit:
        visit = Visit(
            date=target_date,
            vendor_id=v_id,
            distributor_id=vendor.distributor_id,
            supervisor_id=uid,
            # FIX 1: Explicitly initialize all numeric fields to 0
            visites_programmees=0,
            visites_effectuees=0,
            nb_factures=0,
        )
        db.session.add(visit)

    # 3. Update the specific field
    if field == "prog": 
        visit.visites_programmees = val
    elif field == "done": 
        visit.visites_effectuees = val
    elif field == "invoices": 
        visit.nb_factures = val

    try:
        db.session.commit()
        return jsonify({"success": True, "visit_id": visit.id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500