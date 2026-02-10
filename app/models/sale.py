from app.extensions import db
from datetime import datetime


class Sale(db.Model):
    __tablename__ = "sales"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    vendor_id = db.Column(db.Integer, db.ForeignKey("dbo.vendors.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))

    status = db.Column(db.String(20), default="en_cours")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column("montant_total", db.Numeric(18, 2), default=0)

    # Relationships
    items = db.relationship(
        "SaleItem", backref="sale", cascade="all, delete-orphan", lazy=True
    )
    distributor = db.relationship("Distributor", backref="sales")
    vendor = db.relationship("Vendor", backref="sales")
    supervisor = db.relationship("User", backref="supervised_sales")


class SaleItem(db.Model):
    __tablename__ = "sale_items"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("dbo.sales.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("dbo.products.id"))
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship("Product")


class SaleView(db.Model):
    __tablename__ = "vw_sales_list"
    __table_args__ = {"schema": "dbo"}
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    status = db.Column(db.String)
    supervisor_id = db.Column(db.Integer)
    distributor_id = db.Column(db.Integer)
    distributor_name = db.Column("distributeur_nom", db.String)
    vendor_id = db.Column(db.Integer)
    vendor_last_name = db.Column("vendeur_nom", db.String)
    vendor_first_name = db.Column("vendeur_prenom", db.String)
    vendor_type = db.Column("vendeur_type", db.String)
    total_amount = db.Column("montant_total", db.Numeric)
