from flask import request, jsonify
from app.extensions import db
from app.models.geography import Region, Zone, Wilaya
from sqlalchemy.exc import IntegrityError

# --- VALIDATION HELPERS ---


def validate_string(val, name, max_len=100, required=True):
    if not val or not str(val).strip():
        if required:
            return False, f"Le champ '{name}' est obligatoire."
        return True, None
    if len(str(val)) > max_len:
        return False, f"Le champ '{name}' est trop long (max {max_len} caractères)."
    return True, None


def validate_int(val, name):
    try:
        if val is None:
            return False, f"Le champ '{name}' est obligatoire."
        return True, int(val)
    except (ValueError, TypeError):
        return False, f"Le champ '{name}' doit être un nombre valide."


# --- REGIONS ---


def list_regions():
    regions = Region.query.order_by(Region.name.asc()).all()
    return jsonify([{"id": r.id, "name": r.name} for r in regions]), 200


def create_region():
    data = request.json or {}
    ok, msg = validate_string(data.get("name"), "Nom")
    if not ok:
        return jsonify({"message": msg}), 400

    if Region.query.filter_by(name=data["name"].strip()).first():
        return jsonify({"message": "Cette région existe déjà."}), 409

    try:
        new_reg = Region(name=data["name"].strip())
        db.session.add(new_reg)
        db.session.commit()
        return jsonify({"id": new_reg.id, "name": new_reg.name}), 201
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la création."}), 500


def delete_region(id):
    reg = Region.query.get_or_404(id)

    # Dependency check: Regions -> Zones
    if reg.zones:
        zone_names = ", ".join([z.name for z in reg.zones])
        return (
            jsonify(
                {
                    "message": f"Suppression impossible : Cette région contient les zones suivantes : {zone_names}. Supprimez ou réaffectez les zones d'abord."
                }
            ),
            400,
        )

    try:
        db.session.delete(reg)
        db.session.commit()
        return jsonify({"message": f"Région '{reg.name}' supprimée."}), 200
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "message": "Erreur d'intégrité : cette région est encore liée à d'autres données."
                }
            ),
            400,
        )


# --- ZONES ---


def list_zones():
    zones = Zone.query.order_by(Zone.name.asc()).all()
    return (
        jsonify(
            [
                {
                    "id": z.id,
                    "name": z.name,
                    "region_id": z.region_id,
                    "region_name": z.region.name if z.region else "N/A",
                }
                for z in zones
            ]
        ),
        200,
    )


def create_zone():
    data = request.json or {}
    ok, msg = validate_string(data.get("name"), "Nom de zone")
    if not ok:
        return jsonify({"message": msg}), 400

    ok, reg_id = validate_int(data.get("region_id"), "Région")
    if not ok:
        return jsonify({"message": reg_id}), 400

    if not db.session.get(Region, reg_id):
        return jsonify({"message": "La région parente n'existe pas."}), 404

    try:
        new_zone = Zone(name=data["name"].strip(), region_id=reg_id)
        db.session.add(new_zone)
        db.session.commit()
        return jsonify({"id": new_zone.id, "name": new_zone.name}), 201
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la création."}), 500


def delete_zone(id):
    zone = Zone.query.get_or_404(id)

    # Dependency check: Zones -> Wilayas
    if zone.wilayas:
        wilaya_names = ", ".join([w.name for w in zone.wilayas])
        return (
            jsonify(
                {
                    "message": f"Suppression impossible : Cette zone contient les wilayas suivantes : {wilaya_names}. Supprimez ou réaffectez les wilayas d'abord."
                }
            ),
            400,
        )

    try:
        db.session.delete(zone)
        db.session.commit()
        return jsonify({"message": f"Zone '{zone.name}' supprimée."}), 200
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "message": "Erreur d'intégrité : cette zone est encore liée à d'autres données."
                }
            ),
            400,
        )


# --- WILAYAS ---


def list_wilayas():
    wilayas = Wilaya.query.order_by(Wilaya.zone_id, Wilaya.code).all()
    return (
        jsonify(
            [
                {
                    "id": w.id,
                    "name": w.name,
                    "code": w.code,
                    "zone_id": w.zone_id,
                    "zone_name": w.zone.name if w.zone else "N/A",
                    "region_name": (
                        w.zone.region.name if (w.zone and w.zone.region) else "N/A"
                    ),
                }
                for w in wilayas
            ]
        ),
        200,
    )


def create_wilaya():
    data = request.json or {}
    ok, msg = validate_string(data.get("name"), "Nom de la Wilaya")
    if not ok:
        return jsonify({"message": msg}), 400

    ok, code_val = validate_int(data.get("code"), "Code Wilaya")
    if not ok:
        return jsonify({"message": code_val}), 400

    ok, zone_id = validate_int(data.get("zone_id"), "Zone")
    if not ok:
        return jsonify({"message": zone_id}), 400

    if not db.session.get(Zone, zone_id):
        return jsonify({"message": "La zone parente n'existe pas."}), 404

    try:
        new_wilaya = Wilaya(name=data["name"].strip(), code=code_val, zone_id=zone_id)
        db.session.add(new_wilaya)
        db.session.commit()
        return jsonify({"id": new_wilaya.id, "name": new_wilaya.name}), 201
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Erreur lors de la création."}), 500


def delete_wilaya(id):
    wilaya = Wilaya.query.get_or_404(id)

    # 1. Dependency Check: Wilaya -> Distributors
    if wilaya.distributors:
        dist_names = ", ".join([d.name for d in wilaya.distributors])
        return (
            jsonify(
                {
                    "message": f"Suppression impossible : Utilisée par les distributeurs : {dist_names}."
                }
            ),
            400,
        )

    # 2. Dependency Check: Wilaya -> Supervisors
    assigned_supervisors = wilaya.supervisors.all()
    if assigned_supervisors:
        sup_names = ", ".join(
            [f"{s.first_name} {s.last_name}" for s in assigned_supervisors]
        )
        return (
            jsonify(
                {
                    "message": f"Suppression impossible : Affectée aux superviseurs : {sup_names}."
                }
            ),
            400,
        )

    try:
        db.session.delete(wilaya)
        db.session.commit()
        return jsonify({"message": f"Wilaya '{wilaya.name}' supprimée."}), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "Erreur d'intégrité lors de la suppression."}), 400
