from app.extensions import db


class Distributor(db.Model):
    __tablename__ = "distributors"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column("nom", db.String(255), nullable=False)
    wilaya_id = db.Column(db.Integer, db.ForeignKey("dbo.wilayas.id"))
    # REMOVED: supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True)

    # Relationships
    # Note: 'supervisors' relationship is defined via backref in User model
    wilaya = db.relationship("Wilaya", backref="distributors")


class DistributorView(db.Model):
    __tablename__ = "vw_distributor_details"
    __table_args__ = {"schema": "dbo"}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column("nom", db.String)
    active = db.Column(db.Boolean)
    wilaya_id = db.Column(db.Integer)
    wilaya_name = db.Column("wilaya_nom", db.String)
    wilaya_code = db.Column(db.String)
    address = db.Column(db.String)
