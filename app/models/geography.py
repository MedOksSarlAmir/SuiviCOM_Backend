from app.extensions import db


class Region(db.Model):
    __tablename__ = "regions"
    __table_args__ = {"schema": "dbo"}  # <--- MUST BE HERE
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    zones = db.relationship("Zone", backref="region", lazy=True)


class Zone(db.Model):
    __tablename__ = "zones"
    __table_args__ = {"schema": "dbo"}  # <--- MUST BE HERE
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # MUST have dbo. prefix
    region_id = db.Column(db.Integer, db.ForeignKey("dbo.regions.id"))

    wilayas = db.relationship("Wilaya", backref="zone", lazy=True)


class Wilaya(db.Model):
    __tablename__ = "wilayas"
    __table_args__ = {"schema": "dbo"}  # <--- MUST BE HERE
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # MUST have dbo. prefix
    zone_id = db.Column(db.Integer, db.ForeignKey("dbo.zones.id"))
    code = db.Column(db.Integer)
