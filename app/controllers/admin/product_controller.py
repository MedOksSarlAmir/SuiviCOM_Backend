from flask import request, jsonify
from app.extensions import db
from app.models import Product
from app.utils.pagination import paginate
from sqlalchemy import or_


def list_products():
    search = request.args.get("search", "")
    category_id = request.args.get("category_id")

    query = Product.query

    if search:
        query = query.filter(
            or_(Product.name.ilike(f"%{search}%"), Product.code.ilike(f"%{search}%"))
        )

    if category_id and category_id != "all":
        query = query.filter(Product.category_id == category_id)

    paginated_data = paginate(query.order_by(Product.name.asc()))

    return (
        jsonify(
            {
                "data": [
                    {
                        "id": p.id,
                        "code": p.code,
                        "name": p.name,
                        "format": p.format,
                        "category": p.category.name if p.category else None,
                        "price_factory": float(p.price_factory),
                        "active": p.active,
                    }
                    for p in paginated_data["items"]
                ],
                "total": paginated_data["total"],
            }
        ),
        200,
    )


def create_product():
    data = request.json
    new_prod = Product(
        code=data["code"],
        name=data["name"], # Frontend sends 'name', maps to 'designation'
        format=data.get("format"),
        category_id=data["category_id"],
        type_id=data["type_id"],
        price_factory=data.get("price_factory", 0),
        price_wholesale=data.get("price_wholesale", 0),
        price_retail=data.get("price_retail", 0),
        price_supermarket=data.get("price_supermarket", 0),
        active=True,
    )
    db.session.add(new_prod)
    db.session.commit()
    return jsonify({"message": "Produit créé", "id": new_prod.id}), 201

def update_product(product_id):
    prod = Product.query.get_or_404(product_id)
    data = request.json

    prod.name = data.get("name", prod.name)
    prod.format = data.get("format", prod.format)
    prod.price_factory = data.get("price_factory", prod.price_factory)
    prod.price_wholesale = data.get("price_wholesale", prod.price_wholesale)
    prod.price_retail = data.get("price_retail", prod.price_retail)
    prod.price_supermarket = data.get("price_supermarket", prod.price_supermarket)
    prod.active = data.get("active", prod.active)

    db.session.commit()
    return jsonify({"message": "Produit mis à jour"}), 200