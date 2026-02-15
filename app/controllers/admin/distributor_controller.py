from flask import request, jsonify
from app.extensions import db
from app.models import Distributor, DistributorView, User, Wilaya
from app.utils.pagination import paginate


def list_distributors():
    search = request.args.get("search", "")
    status = request.args.get("status", "all")
    wilaya_id = request.args.get("wilaya_id")
    supervisor_id = request.args.get("supervisor_id")  # Filter by a specific supervisor

    # We use the View for basic details but we'll need the Model for relationships
    query = Distributor.query

    # 1. Filters
    if search:
        query = query.filter(Distributor.name.ilike(f"%{search}%"))

    if status == "active":
        query = query.filter(Distributor.active == True)
    elif status == "inactive":
        query = query.filter(Distributor.active == False)

    if wilaya_id and wilaya_id != "all":
        query = query.filter(Distributor.wilaya_id == wilaya_id)

    # 🔹 NEW: Filter by supervisor using the Many-to-Many relationship
    if supervisor_id and supervisor_id != "all":
        query = query.join(Distributor.supervisors).filter(User.id == supervisor_id)

    paginated_data = paginate(query.order_by(Distributor.id.desc()))

    results = []
    for d in paginated_data["items"]:
        # Map all supervisors assigned to this distributor
        sups = [
            {"id": s.id, "name": f"{s.last_name} {s.first_name}"} for s in d.supervisors
        ]

        results.append(
            {
                "id": d.id,
                "name": d.name,
                "active": d.active,
                "wilaya_id": d.wilaya_id,
                "wilaya_name": d.wilaya.name if d.wilaya else "N/A",
                "wilaya_code": d.wilaya.code if d.wilaya else "N/A",
                "supervisors": sups,  # Return the whole list
                "address": d.address,
            }
        )

    return jsonify({"data": results, "total": paginated_data["total"]}), 200


def create_distributor():
    data = request.json or {}

    if not data.get("name") or not data.get("wilaya_id"):
        return jsonify({"message": "Nom et Wilaya sont obligatoires."}), 400

    try:
        new_dist = Distributor(
            name=data["name"].strip(),
            wilaya_id=data["wilaya_id"],
            address=data.get("address", "").strip(),
            email=data.get("email", "").strip(),
            active=True,
        )

        # 🔹 Handle multiple supervisor assignments
        sup_ids = data.get("supervisor_ids", [])
        if data.get("supervisor_id"):  # Compatibility with old single-id frontend
            sup_ids.append(data.get("supervisor_id"))

        if sup_ids:
            supervisors = User.query.filter(
                User.id.in_(sup_ids), User.role == "superviseur"
            ).all()
            new_dist.supervisors = supervisors

        db.session.add(new_dist)
        db.session.commit()
        return jsonify({"message": "Distributeur créé", "id": new_dist.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erreur: {str(e)}"}), 500


def update_distributor(dist_id):
    dist = Distributor.query.get_or_404(dist_id)
    data = request.json or {}

    dist.name = data.get("name", dist.name).strip()
    dist.wilaya_id = data.get("wilaya_id", dist.wilaya_id)
    dist.active = data.get("active", dist.active)
    dist.address = data.get("address", dist.address).strip()

    # 🔹 Sync Supervisors (Many-to-Many)
    if "supervisor_ids" in data:
        sup_ids = data.get("supervisor_ids", [])
        supervisors = User.query.filter(
            User.id.in_(sup_ids), User.role == "superviseur"
        ).all()
        dist.supervisors = supervisors
    elif "supervisor_id" in data:  # Compatibility fallback
        sid = data.get("supervisor_id")
        if sid:
            sup = User.query.get(sid)
            if sup and sup.role == "superviseur":
                dist.supervisors = [sup]
        else:
            dist.supervisors = []

    try:
        db.session.commit()
        return jsonify({"message": "Distributeur mis à jour."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la mise à jour."}), 500


def bulk_reassign():
    """Add a supervisor to multiple distributors without removing existing ones"""
    data = request.json or {}
    dist_ids = data.get("distributor_ids", [])
    new_sup_id = data.get("supervisor_id")

    sup = db.session.get(User, new_sup_id)
    if not sup or sup.role != "superviseur":
        return jsonify({"message": "Le destinataire doit être un superviseur."}), 400

    try:
        dists = Distributor.query.filter(Distributor.id.in_(dist_ids)).all()
        for d in dists:
            if sup not in d.supervisors:
                d.supervisors.append(sup)
        db.session.commit()
        return (
            jsonify({"message": f"Superviseur ajouté à {len(dists)} distributeurs."}),
            200,
        )
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la réassignation groupée."}), 500


def list_supervisors():
    supervisors = (
        User.query.filter(User.role == "superviseur")
        .order_by(User.last_name, User.first_name)
        .all()
    )
    return (
        jsonify(
            {
                "data": [
                    {
                        "id": u.id,
                        "first_name": u.first_name,
                        "last_name": u.last_name,
                        "zone_id": u.zone_id,
                    }
                    for u in supervisors
                ]
            }
        ),
        200,
    )
