from app.extensions import ma
from app.models.sale import Sale, SaleItem
from app.models.purchase import Purchase, PurchaseItem


class SaleItemSchema(ma.SQLAlchemyAutoSchema):
    product_name = ma.String(attribute="product.name", dump_only=True)
    product_code = ma.String(attribute="product.code", dump_only=True)

    class Meta:
        model = SaleItem
        include_fk = True


class SaleSchema(ma.SQLAlchemyAutoSchema):
    items = ma.Nested(SaleItemSchema, many=True)
    distributor_name = ma.String(attribute="distributor.name", dump_only=True)
    vendor_name = ma.Method("get_vendor_full_name")

    def get_vendor_full_name(self, obj):
        if obj.vendor:
            return f"{obj.vendor.first_name} {obj.vendor.last_name}"
        return None

    class Meta:
        model = Sale
        include_fk = True


class PurchaseItemSchema(ma.SQLAlchemyAutoSchema):
    product_name = ma.String(attribute="product.name", dump_only=True)

    class Meta:
        model = PurchaseItem
        include_fk = True


class PurchaseSchema(ma.SQLAlchemyAutoSchema):
    items = ma.Nested(PurchaseItemSchema, many=True)
    distributor_name = ma.String(attribute="distributor.name", dump_only=True)

    class Meta:
        model = Purchase
        include_fk = True
