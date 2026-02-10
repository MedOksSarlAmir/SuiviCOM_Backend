from app.extensions import db


class ProductCategory(db.Model):
    __tablename__ = "product_categories"
    __table_args__ = {"schema": "dbo"}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


class ProductType(db.Model):
    __tablename__ = "product_types"
    __table_args__ = {"schema": "dbo"}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = {"schema": "dbo"}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)
    name = db.Column("designation", db.String(255))
    format = db.Column(db.String(50))
    category_id = db.Column(db.Integer, db.ForeignKey("dbo.product_categories.id"))
    type_id = db.Column(db.Integer, db.ForeignKey("dbo.product_types.id"))
    active = db.Column(db.Boolean, default=True)

    price_factory = db.Column(db.Numeric(10, 2), default=0)
    price_wholesale = db.Column("price_gros", db.Numeric(10, 2), default=0)
    price_retail = db.Column("price_detail", db.Numeric(10, 2), default=0)
    price_supermarket = db.Column("price_superette", db.Numeric(10, 2), default=0)

    category = db.relationship("ProductCategory", backref="products")
    type = db.relationship("ProductType", backref="products")
