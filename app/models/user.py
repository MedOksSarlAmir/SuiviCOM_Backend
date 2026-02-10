from app.extensions import db
from datetime import datetime


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    last_name = db.Column("nom", db.String(100))
    first_name = db.Column("prenom", db.String(100))
    role = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)

    # ALL THREE MUST HAVE dbo. PREFIX
    region_id = db.Column(db.Integer, db.ForeignKey("dbo.regions.id"), nullable=True)
    zone_id = db.Column(db.Integer, db.ForeignKey("dbo.zones.id"), nullable=True)
    wilaya_id = db.Column(db.Integer, db.ForeignKey("dbo.wilayas.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to the classes
    region = db.relationship("Region", backref="users")
    zone = db.relationship("Zone", backref="users")
    wilaya = db.relationship("Wilaya", backref="users")

    def to_dict(self):
        ROLE_GEO_SCOPE = {
            "superviseur": "Wilaya",
            "chef_zone": "Zone",
            "regional": "Region",
            "dc": "National",
            "dg": "National",
            "admin": "System",
        }

        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "last_name": self.last_name,
            "first_name": self.first_name,
            "active": self.active,
            "geo_scope": ROLE_GEO_SCOPE.get(self.role, "N/A"),
            "region": self.region.name if self.region else None,
            "zone": self.zone.name if self.zone else None,
            "wilaya": self.wilaya.name if self.wilaya else None,
        }
