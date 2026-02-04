import pytest
import uuid
from app.models import Product, ProductCategory


def test_category_format_hierarchy(client, auth_headers, db):
    # 1. Setup: Category with unique product codes
    cat_name = f"Cat_{uuid.uuid4().hex[:4]}"
    cat = ProductCategory(name=cat_name)
    db.session.add(cat)
    db.session.flush()

    p1_code = f"PC1_{uuid.uuid4().hex[:4]}"
    p2_code = f"PC2_{uuid.uuid4().hex[:4]}"

    p1 = Product(
        code=p1_code,
        designation="Cola 1L",
        format="1L",
        category_id=cat.id,
        active=True,
    )
    p2 = Product(
        code=p2_code,
        designation="Cola 33cl",
        format="33cl",
        category_id=cat.id,
        active=True,
    )
    db.session.add_all([p1, p2])
    db.session.commit()

    # 2. Action: Get filters
    response = client.get(
        "/api/v1/supervisor/categories-with-formats",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200
    data = response.json

    # Find our specific category in the list
    cat_entry = next(c for c in data if c["name"] == cat_name)
    assert "1L" in cat_entry["formats"]
    assert "33cl" in cat_entry["formats"]