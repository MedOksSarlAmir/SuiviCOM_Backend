from flask import request, jsonify
from app.extensions import db, bcrypt
from app.models import User, Wilaya, Zone, Region, Distributor
from app.utils.pagination import paginate
from sqlalchemy import or_


def list_users():
    search = request.args.get("search", "")
    role_filter = request.args.get("role", "all")

    query = User.query

    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
            )
        )

    if role_filter != "all":
        query = query.filter(User.role == role_filter)

    paginated_data = paginate(query.order_by(User.created_at.desc()))

    results = []
    for u in paginated_data["items"]:
        u_dict = u.to_dict()
        results.append(u_dict)

    return jsonify({"data": results, "total": paginated_data["total"]}), 200


def create_user():
    data = request.json or {}

    if not data.get("username") or not data.get("password") or not data.get("role"):
        return jsonify({"message": "Données obligatoires manquantes."}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"message": "Ce nom d'utilisateur est déjà pris."}), 409

    new_user = User(
        username=data["username"],
        password_hash=bcrypt.generate_password_hash(data["password"]).decode("utf-8"),
        role=data["role"],
        last_name=data.get("last_name", "").strip(),
        first_name=data.get("first_name", "").strip(),
        phone=data.get("phone"),
        active=True,
    )

    # 🔹 FIX: Add to session BEFORE handling scoping to avoid SAWarning
    db.session.add(new_user)

    err = _handle_user_scoping(new_user, data)
    if err:
        db.session.rollback()  # Rollback since we already added to session
        return jsonify({"message": err}), 400

    try:
        db.session.commit()
        return jsonify({"message": "Utilisateur créé", "id": new_user.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erreur: {str(e)}"}), 500


def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json or {}

    user.last_name = data.get("last_name", user.last_name).strip()
    user.first_name = data.get("first_name", user.first_name).strip()
    user.role = data.get("role", user.role)
    user.phone = data.get("phone", user.phone)
    user.active = data.get("active", user.active)

    if data.get("password"):
        user.password_hash = bcrypt.generate_password_hash(data["password"]).decode(
            "utf-8"
        )

    err = _handle_user_scoping(user, data)
    if err:
        return jsonify({"message": err}), 400

    try:
        db.session.commit()
        return jsonify({"message": "Utilisateur mis à jour."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la mise à jour."}), 500


def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    # 🔹 FIX: Use .count() instead of len() for dynamic relationships
    orphaned_dists = []
    for d in user.supervised_distributors:
        if d.supervisors.count() == 1:  # Only this user manages it
            orphaned_dists.append(d.name)

    if orphaned_dists:
        return (
            jsonify(
                {
                    "message": f"Action bloquée : ce superviseur est le seul assigné aux distributeurs : {', '.join(orphaned_dists)}. Réaffectez-les d'abord."
                }
            ),
            400,
        )

    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "Utilisateur supprimé."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erreur lors de la suppression: {str(e)}"}), 500


def _handle_user_scoping(user, data):
    role = data.get("role")
    user.region_id = None
    user.zone_id = None
    user.assigned_wilayas = []

    if role in ["dg", "dc", "admin"]:
        return None

    if role == "regional":
        if not data.get("region_id"):
            return "Région requise."
        user.region_id = data.get("region_id")

    elif role == "chef_zone":
        if not data.get("zone_id"):
            return "Zone requise."
        zone = db.session.get(Zone, data["zone_id"])
        if not zone:
            return "Zone introuvable."
        user.zone_id = zone.id
        user.region_id = zone.region_id

    elif role == "superviseur":
        w_ids = data.get("wilaya_ids", [])
        if not w_ids:
            return "Wilayas requises."

        wilayas = Wilaya.query.filter(Wilaya.id.in_(w_ids)).all()
        user.assigned_wilayas = wilayas

        if wilayas:
            user.zone_id = wilayas[0].zone_id
            user.region_id = wilayas[0].zone.region_id

        # Handle Distributor Assignments directly if provided
        if "distributeur_ids" in data:
            d_ids = data.get("distributeur_ids", [])
            user.supervised_distributors = Distributor.query.filter(
                Distributor.id.in_(d_ids)
            ).all()

    return None
