from app.extensions import db
from datetime import datetime


class Purchase(db.Model):
    __tablename__ = "purchases"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))

    total_amount = db.Column("montant_total", db.Numeric(18, 2), default=0)
    status = db.Column(db.String(20), default="en_cours")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship(
        "PurchaseItem", backref="purchase", cascade="all, delete-orphan", lazy=True
    )
    distributor = db.relationship("Distributor", backref="purchases")
    supervisor = db.relationship("User", backref="supervised_purchases")


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("dbo.purchases.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("dbo.products.id"))
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship("Product")


class PurchaseView(db.Model):
    __tablename__ = "vw_purchases_list"
    __table_args__ = {"schema": "dbo"}
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    status = db.Column(db.String)
    total_amount = db.Column("montant_total", db.Numeric)
    supervisor_id = db.Column(db.Integer)
    distributor_id = db.Column(db.Integer)
    distributor_name = db.Column("distributeur_nom", db.String)
