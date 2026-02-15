from app.extensions import db


class Vendor(db.Model):
    __tablename__ = "vendors"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)
    last_name = db.Column("nom", db.String(100))
    first_name = db.Column("prenom", db.String(100))
    vendor_type = db.Column("vendor_type", db.String(20))  # gros, detail, superette
    created_at = db.Column(db.DateTime, default=db.func.now())

    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    # We keep this for individual vendor assignment,
    # but security will also check distributor access.
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))
    active = db.Column(db.Boolean, default=True)

    # Relationships
    distributor = db.relationship("Distributor", backref="vendors")
    supervisor = db.relationship("User", backref="supervised_vendors")
