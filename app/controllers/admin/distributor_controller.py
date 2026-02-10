from flask import request, jsonify
from app.extensions import db
from app.models import Distributor, DistributorView, User
from app.utils.pagination import paginate
from app.schemas import DistributorSchema # (You'd need to add this to schemas)
dist_schema = DistributorSchema(many=True)

def list_distributors():
    # Use the View for listing to get Wilaya names easily
    query = DistributorView.query

    # Optional filtering by active/inactive for Admin
    status = request.args.get("status", "all")
    if status == "active":
        query = query.filter(DistributorView.active == True)
    elif status == "inactive":
        query = query.filter(DistributorView.active == False)

    # Search
    search = request.args.get("search", "")
    if search:
        query = query.filter(DistributorView.name.ilike(f"%{search}%"))

    paginated_data = paginate(query)


    return jsonify({
        "data": dist_schema.dump(paginated_data["items"]),
        "total": paginated_data["total"]
    })

def create_distributor():
    data = request.json
    new_dist = Distributor(
        name=data["name"],
        wilaya_id=data["wilaya_id"],
        supervisor_id=data.get("supervisor_id"),
        address=data.get("address"),
        phone=data.get("phone"),
        email=data.get("email"),
        active=True,
    )
    db.session.add(new_dist)
    db.session.commit()
    return jsonify({"message": "Distributor created", "id": new_dist.id}), 201


def update_distributor(dist_id):
    dist = Distributor.query.get_or_404(dist_id)
    data = request.json

    dist.name = data.get("name", dist.name)
    dist.supervisor_id = data.get("supervisor_id", dist.supervisor_id)
    dist.active = data.get("active", dist.active)
    dist.wilaya_id = data.get("wilaya_id", dist.wilaya_id)

    db.session.commit()
    return jsonify({"message": "Distributor updated"}), 200


def bulk_reassign_distributors():
    """Admin feature to move multiple distributors to a new supervisor"""
    data = request.json
    distributor_ids = data.get("distributor_ids", [])
    new_supervisor_id = data.get("supervisor_id")

    if not distributor_ids or not new_supervisor_id:
        return jsonify({"message": "Missing data"}), 400

    Distributor.query.filter(Distributor.id.in_(distributor_ids)).update(
        {Distributor.supervisor_id: new_supervisor_id}, synchronize_session=False
    )
    db.session.commit()
    return jsonify({"message": f"{len(distributor_ids)} distributors reassigned"}), 200
