from app.extensions import db


class Inventory(db.Model):
    __tablename__ = "inventory"
    __table_args__ = {"schema": "dbo"}

    distributor_id = db.Column(
        db.Integer, db.ForeignKey("dbo.distributors.id"), primary_key=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("dbo.products.id"), primary_key=True
    )
    quantity = db.Column("stock_qte", db.Integer, default=0)
    last_updated = db.Column(db.DateTime)

    product = db.relationship("Product")
    distributor = db.relationship("Distributor")


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

    supervisor = db.relationship("User")



class InventoryHistoryView(db.Model):
    __tablename__ = "vw_inventory_history"
    __table_args__ = {"extend_existing": True, "schema": "dbo"}

    ref_id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, primary_key=True)
    created_at = db.Column(db.DateTime)
    vendor_id = db.Column(db.Integer)

    distributor_id = db.Column(db.Integer)
    product_id = db.Column(db.Integer)
    quantity = db.Column("qte", db.Integer)
    actor_name = db.Column(db.String)
    note = db.Column(db.String)


class PhysicalInventory(db.Model):
    __tablename__ = "physical_inventory"
    __table_args__ = {"schema": "dbo"}

    distributor_id = db.Column(
        db.Integer, db.ForeignKey("dbo.distributors.id"), primary_key=True
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("dbo.products.id"), primary_key=True
    )
    quantity = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    product = db.relationship("Product")
