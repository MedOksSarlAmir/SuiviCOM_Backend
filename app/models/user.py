from app.extensions import db
from datetime import datetime


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = {"schema": "dbo"}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    role = db.Column(
        db.String(20), nullable=False
    )  # admin, dg, dc, regional, chef_zone, superviseur
    phone = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)

    # Hierarchy
    region_id = db.Column(db.Integer, db.ForeignKey("regions.id"), nullable=True)
    zone_id = db.Column(db.Integer, db.ForeignKey("zones.id"), nullable=True)
    wilaya_id = db.Column(db.Integer, db.ForeignKey("wilayas.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    region = db.relationship("Region", backref="users")
    zone = db.relationship("Zone", backref="users")
    wilaya = db.relationship("Wilaya", backref="users")


    def to_dict(self):
        ROLE_GEO_SCOPE = {
            "superviseur": "WILAYA",
            "chefzone": "ZONE",
            "regional": "REGION",
        }

        geo_scope = ROLE_GEO_SCOPE.get(self.role)

        data = {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "nom": self.nom,
            "prenom": self.prenom,
        }

        if geo_scope == "WILAYA":
            data["geo_scope"] = "Wilaya"
            data["wilaya"] = self.wilaya.name if self.wilaya else None

        elif geo_scope == "ZONE":
            data["geo_scope"] = "Zone"
            data["zone"] = self.zone.name if self.zone else None

        elif geo_scope == "REGION":
            data["geo_scope"] = "Région"
            data["region"] = self.region.name if self.region else None

        return data