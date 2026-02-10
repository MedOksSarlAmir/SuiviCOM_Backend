from app.extensions import ma
from app.models.product import Product


class ProductSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Product
        load_instance = True

    # Map the display name to 'name' but accept 'designation' if needed
    category_name = ma.String(attribute="category.name", dump_only=True)
