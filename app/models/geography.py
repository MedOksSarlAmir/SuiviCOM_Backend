from app.extensions import db


class Region(db.Model):
    __tablename__ = "regions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # One region has many zones
    zones = db.relationship("Zone", backref="region", lazy=True)


class Zone(db.Model):
    __tablename__ = "zones"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    region_id = db.Column(db.Integer, db.ForeignKey("regions.id"))

    # One zone has many wilayas
    wilayas = db.relationship("Wilaya", backref="zone", lazy=True)


class Wilaya(db.Model):
    __tablename__ = "wilayas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    zone_id = db.Column(db.Integer, db.ForeignKey("zones.id"))
