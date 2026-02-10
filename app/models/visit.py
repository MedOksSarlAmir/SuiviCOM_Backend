from app.extensions import db
from datetime import datetime


class Visit(db.Model):
    __tablename__ = "visits"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    vendor_id = db.Column(db.Integer, db.ForeignKey("dbo.vendors.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))

    planned_visits = db.Column("visites_programmees", db.Integer, default=0)
    actual_visits = db.Column("visites_effectuees", db.Integer, default=0)
    invoice_count = db.Column("nb_factures", db.Integer, default=0)

    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    distributor = db.relationship("Distributor", backref="visits_activity")
    vendor = db.relationship("Vendor", backref="visits_activity")
    supervisor = db.relationship("User", backref="created_visits")


class VisitView(db.Model):
    __tablename__ = "vw_visits_list"
    __table_args__ = {"schema": "dbo"}
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    planned_visits = db.Column("visites_programmees", db.Integer)
    actual_visits = db.Column("visites_effectuees", db.Integer)
    invoice_count = db.Column("nb_factures", db.Integer)
    supervisor_id = db.Column(db.Integer)
    distributor_id = db.Column(db.Integer)
    distributor_name = db.Column("distributeur_nom", db.String)
    vendor_id = db.Column(db.Integer)
    vendor_last_name = db.Column("vendeur_nom", db.String)
    vendor_first_name = db.Column("vendeur_prenom", db.String)
