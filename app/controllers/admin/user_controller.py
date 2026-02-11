from flask import request, jsonify
from app.extensions import db, bcrypt
from app.models import User
from app.utils.pagination import paginate
from sqlalchemy import or_
from app.schemas import UserSchema

user_schema = UserSchema(many=True)


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

    query = query.order_by(User.created_at.desc())

    paginated_data = paginate(query)

    return (
        jsonify(
            {
                "data": user_schema.dump(paginated_data["items"]),
                "total": paginated_data["total"],
            }
        ),
        200,
    )


def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json

    user.last_name = data.get("last_name", user.last_name)
    user.first_name = data.get("first_name", user.first_name)
    user.role = data.get("role", user.role)
    user.phone = data.get("phone", user.phone)
    user.active = data.get("active", user.active)

    # Geo update
    user.region_id = data.get("region_id", user.region_id)
    user.zone_id = data.get("zone_id", user.zone_id)
    if "wilaya_ids" in data:
        from app.models.geography import Wilaya

        # Clear existing and add new
        new_wilayas = Wilaya.query.filter(Wilaya.id.in_(data["wilaya_ids"])).all()
        user.assigned_wilayas = new_wilayas

    db.session.commit()
    if data.get("password"):
        user.password_hash = bcrypt.generate_password_hash(data["password"]).decode(
            "utf-8"
        )

    db.session.commit()
    return jsonify({"message": "Utilisateur mis à jour"}), 200


def create_user():
    data = request.json
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"message": "Nom d'utilisateur déjà pris"}), 400

    new_user = User(
        username=data["username"],
        password_hash=bcrypt.generate_password_hash(data["password"]).decode("utf-8"),
        role=data["role"],
        last_name=data.get("last_name"),  # maps to nom
        first_name=data.get("first_name"),  # maps to prenom
        phone=data.get("phone"),
        region_id=data.get("region_id"),
        zone_id=data.get("zone_id"),
        wilaya_id=data.get("wilaya_id"),
        active=True,
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Utilisateur créé", "id": new_user.id}), 201


def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    # 🔹 RESTORED: Dependency Check
    if user.supervised_distributors or user.supervised_sales:
        return (
            jsonify(
                {
                    "message": "Impossible de supprimer: cet utilisateur a des données liées (Distributeurs ou Ventes). Désactivez-le à la place."
                }
            ),
            400,
        )

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Utilisateur supprimé"}), 200
