from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import or_
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
