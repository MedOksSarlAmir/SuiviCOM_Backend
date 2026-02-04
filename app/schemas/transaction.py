from app.extensions import ma
from app.models.supervisor import Sale, SaleItem, Purchase, PurchaseItem, Product


class ProductSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Product
        load_instance = True


class SaleItemSchema(ma.SQLAlchemyAutoSchema):
    product = ma.Nested(ProductSchema, only=("designation", "code"))

    class Meta:
        model = SaleItem
        load_instance = True
        include_fk = True


class SaleSchema(ma.SQLAlchemyAutoSchema):
    items = ma.Nested(SaleItemSchema, many=True)
    distributeur_nom = ma.String(attribute="distributor.nom", dump_only=True)
    vendeur_nom = ma.String(attribute="vendor.nom", dump_only=True)

    class Meta:
        model = Sale
        load_instance = True
        include_fk = True


class PurchaseItemSchema(ma.SQLAlchemyAutoSchema):
    product = ma.Nested(ProductSchema, only=("designation", "code"))

    class Meta:
        model = PurchaseItem
        load_instance = True
        include_fk = True


class PurchaseSchema(ma.SQLAlchemyAutoSchema):
    items = ma.Nested(PurchaseItemSchema, many=True)
    distributeur_nom = ma.String(attribute="distributor.nom", dump_only=True)

    class Meta:
        model = Purchase
        load_instance = True
        include_fk = True
