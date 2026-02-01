from app.extensions import db
from datetime import datetime


# =========================
# DISTRIBUTOR
# =========================
class Distributor(db.Model):
    __tablename__ = "distributors"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    wilaya_id = db.Column(db.Integer, db.ForeignKey("dbo.wilayas.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True)

    supervisor = db.relationship("User", backref="distributors_supervised")
    vendors = db.relationship("Vendor", backref="distributor", lazy=True)
    inventory_records = db.relationship("Inventory", backref="distributor", lazy=True)
    stock_adjustments = db.relationship(
        "StockAdjustment", backref="distributor", lazy=True
    )


# =========================
# VENDOR
# =========================
class Vendor(db.Model):
    __tablename__ = "vendors"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    code = db.Column(db.String(50))
    vendor_type = db.Column(db.String(20))  # gros, detail, superette
    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))
    active = db.Column(db.Boolean, default=True)

    supervisor = db.relationship("User", backref="vendors_supervised")


# =========================
# PRODUCT CATEGORY
# =========================
class ProductCategory(db.Model):
    __tablename__ = "product_categories"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    products = db.relationship("Product", backref="category", lazy=True)


# =========================
# PRODUCT TYPE
# =========================
class ProductType(db.Model):
    __tablename__ = "product_types"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    products = db.relationship("Product", backref="type", lazy=True)


# =========================
# PRODUCT
# =========================
class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)
    designation = db.Column(db.String(255))
    format = db.Column(db.String(50))
    category_id = db.Column(db.Integer, db.ForeignKey("dbo.product_categories.id"))
    type_id = db.Column(db.Integer, db.ForeignKey("dbo.product_types.id"))

    price_factory = db.Column(db.Numeric(10, 2), default=0)
    price_gros = db.Column(db.Numeric(10, 2), default=0)
    price_detail = db.Column(db.Numeric(10, 2), default=0)
    price_superette = db.Column(db.Numeric(10, 2), default=0)
    active = db.Column(db.Boolean, default=True)


# =========================
# INVENTORY
# =========================
class Inventory(db.Model):
    __tablename__ = "inventory"
    __table_args__ = {"schema": "dbo"}

    distributor_id = db.Column(
        db.Integer, db.ForeignKey("dbo.distributors.id"), primary_key=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("dbo.products.id"), primary_key=True
    )

    stock_qte = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime)
    product = db.relationship("Product", backref="inventory_records", lazy=True)


# =========================
# STOCK ADJUSTMENTS
# =========================
class StockAdjustment(db.Model):
    __tablename__ = "stock_adjustments"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("dbo.products.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))
    quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    supervisor = db.relationship("User", backref="stock_adjustments")


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
    montant_total = db.Column(db.Numeric(18, 2), default=0)

    # Relationships
    items = db.relationship(
        "SaleItem", backref="sale", cascade="all, delete-orphan", lazy=True
    )

    distributor = db.relationship("Distributor", backref="sales")
    vendor = db.relationship("Vendor", backref="sales")
    supervisor = db.relationship("User", backref="sales_supervised")


# =========================
# SALE ITEMS (Lines)
# =========================
class SaleItem(db.Model):
    __tablename__ = "sale_items"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("dbo.sales.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("dbo.products.id"))
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship("Product", backref="sale_items")


# =========================
# PURCHASE (Header)
# =========================
class Purchase(db.Model):
    __tablename__ = "purchases"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))
    montant_total = db.Column(db.Numeric(18, 2), default=0)
    status = db.Column(db.String(20), default="en_cours")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    items = db.relationship(
        "PurchaseItem", backref="purchase", cascade="all, delete-orphan", lazy=True
    )

    distributor = db.relationship("Distributor", backref="purchases")
    supervisor = db.relationship("User", backref="purchases_supervised")


# =========================
# PURCHASE ITEMS (Lines)
# =========================
class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("dbo.purchases.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("dbo.products.id"))
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship("Product", backref="purchase_items")


class SaleView(db.Model):
    __tablename__ = "vw_sales_list"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    status = db.Column(db.String)
    supervisor_id = db.Column(db.Integer)
    distributor_id = db.Column(db.Integer)
    distributeur_nom = db.Column(db.String)
    vendor_id = db.Column(db.Integer)
    vendeur_nom = db.Column(db.String)
    vendeur_prenom = db.Column(db.String)
    vendeur_type = db.Column(db.String)
    montant_total = db.Column(db.Numeric)


class PurchaseView(db.Model):
    __tablename__ = "vw_purchases_list"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    status = db.Column(db.String)
    montant_total = db.Column(db.Numeric)
    supervisor_id = db.Column(db.Integer)
    distributor_id = db.Column(db.Integer)
    distributeur_nom = db.Column(db.String)


class ProductView(db.Model):
    __tablename__ = "vw_product_details"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String)
    designation = db.Column(db.String)
    price_factory = db.Column(db.Numeric)
    price_gros = db.Column(db.Numeric)
    price_detail = db.Column(db.Numeric)
    price_superette = db.Column(db.Numeric)
    active = db.Column(db.Boolean)
    category_name = db.Column(db.String)


class DistributorView(db.Model):
    __tablename__ = "vw_distributor_details"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String)
    active = db.Column(db.Numeric)
    supervisor_id = db.Column(db.Integer)
    wilaya_nom = db.Column(db.Numeric)
    wilaya_code = db.Column(db.String)


class InventoryHistoryView(db.Model):
    __tablename__ = "vw_inventory_history"
    __table_args__ = {"extend_existing": True}
    ref_id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, primary_key=True)
    date = db.Column(db.DateTime)
    distributor_id = db.Column(db.Integer)
    product_id = db.Column(db.Integer)
    qte = db.Column(db.Integer)
    actor_name = db.Column(db.String)
    note = db.Column(db.String)


# Add these to app/models/supervisor.py


class Visit(db.Model):
    __tablename__ = "visits"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    distributor_id = db.Column(db.Integer, db.ForeignKey("dbo.distributors.id"))
    vendor_id = db.Column(db.Integer, db.ForeignKey("dbo.vendors.id"))
    supervisor_id = db.Column(db.Integer, db.ForeignKey("dbo.users.id"))

    visites_programmees = db.Column(db.Integer, default=0)
    visites_effectuees = db.Column(db.Integer, default=0)
    nb_factures = db.Column(db.Integer, default=0)

    status = db.Column(db.String(50), default="programmées/non effectuée")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    distributor = db.relationship("Distributor", backref="visits")
    vendor = db.relationship("Vendor", backref="visits")
    supervisor = db.relationship("User", backref="visits_created")


class VisitView(db.Model):
    __tablename__ = "vw_visits_list"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    status = db.Column(db.String)
    visites_programmees = db.Column(db.Integer)
    visites_effectuees = db.Column(db.Integer)
    nb_factures = db.Column(db.Integer)
    supervisor_id = db.Column(db.Integer)
    distributor_id = db.Column(db.Integer)
    distributeur_nom = db.Column(db.String)
    vendor_id = db.Column(db.Integer)
    vendeur_nom = db.Column(db.String)
    vendeur_prenom = db.Column(db.String)
