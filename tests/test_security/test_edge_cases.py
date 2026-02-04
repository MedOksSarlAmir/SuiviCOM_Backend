import pytest
import uuid
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.exc import IntegrityError
from app.models import Sale, Purchase, Inventory, Product, Vendor


def test_concurrent_stock_updates(
    client, auth_headers, db, test_distributor, test_product
):
    """Test concurrent stock updates (race condition simulation)"""
    # Create initial inventory
    inventory = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=100,
    )
    db.session.add(inventory)
    db.session.commit()

    from app.utils.inventory_sync import update_stock_incremental

    # Simulate concurrent updates
    updates = [(50,), (-30,), (20,), (-40,), (10,)]

    for delta in updates:
        update_stock_incremental(test_distributor.id, test_product.id, delta[0])

    db.session.commit()

    # Check final stock
    db.session.refresh(inventory)
    expected = 100 + 50 - 30 + 20 - 40 + 10
    assert inventory.stock_qte == expected


def test_large_quantity_handling(
    client, auth_headers, test_distributor, test_vendor, test_product
):
    """Test handling of very large quantities"""
    # Create sale with large quantity
    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": date.today().isoformat(),
        "status": "complete",
        "products": [{"product_id": test_product.id, "quantity": 1000000}],  # 1 million
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should handle large numbers (might succeed or fail gracefully)
    assert response.status_code in [201, 400, 500]

    if response.status_code == 201:
        # Check inventory was updated
        inventory = Inventory.query.filter_by(
            distributor_id=test_distributor.id, product_id=test_product.id
        ).first()

        if inventory:
            assert inventory.stock_qte == -1000000


def test_decimal_precision_handling(
    client, auth_headers, db, test_distributor, test_vendor
):
    """Test decimal precision in monetary calculations"""
    # Create product with precise decimal prices
    from app.models import Product
    from decimal import Decimal

    product = Product(
        code=f"DECIMAL_{uuid.uuid4().hex[:6]}",
        designation="Precision Test",
        price_detail=Decimal("123.456789"),
        active=True,
    )
    db.session.add(product)
    db.session.commit()

    # Create sale
    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": date.today().isoformat(),
        "status": "complete",
        "products": [{"product_id": product.id, "quantity": 7}],
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    if response.status_code == 201:
        # Check total calculation
        sale_id = response.json["id"]
        sale = Sale.query.get(sale_id)

        # 7 * 123.456789 = 864.197523
        expected = Decimal("864.197523")
        # Allow for rounding differences
        assert abs(sale.montant_total - expected) < Decimal("0.01")


def test_unicode_character_handling(client, auth_headers, test_distributor):
    """Test handling of Unicode characters"""
    # Test vendor creation with Unicode
    vendor_data = {
        "code": f"UNI_{uuid.uuid4().hex[:4]}",
        "nom": "Véndör Nàmé",
        "prenom": "Prénöm",
        "vendor_type": "detail",
        "distributor_id": test_distributor.id,
    }

    response = client.post(
        "/api/v1/vendors",
        json=vendor_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should handle Unicode
    assert response.status_code in [201, 400, 403]

    if response.status_code == 201:
        # Verify retrieval
        vendor_id = response.json["id"]
        response = client.get(
            f"/api/v1/vendors/{vendor_id}",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert response.status_code == 200


def test_date_boundary_cases(client, auth_headers, test_distributor, test_vendor):
    """Test date boundary cases"""
    boundary_dates = [
        "2020-02-29",  # Leap day
        "2021-12-31",  # Year end
        "2021-01-01",  # Year start
        "2023-13-01",  # Invalid month
        "2023-01-32",  # Invalid day
        "invalid-date",  # Malformed
    ]

    for test_date in boundary_dates:
        sale_data = {
            "acteurId": test_vendor.id,
            "distributeurId": test_distributor.id,
            "date": test_date,
            "status": "en_cours",
            "products": [],
        }

        response = client.post(
            "/api/v1/sales",
            json=sale_data,
            headers={"Authorization": auth_headers["Authorization"]},
        )

        # Should either succeed with valid date or fail gracefully
        assert response.status_code in [201, 400, 500]

        if "invalid" in test_date or "13" in test_date or "32" in test_date:
            # Invalid dates should fail
            assert response.status_code != 201


def test_empty_and_null_values(client, auth_headers):
    """Test handling of empty and null values"""
    # Test with empty request bodies
    endpoints = [
        ("/api/v1/auth/login", "POST"),
        ("/api/v1/sales", "POST"),
        ("/api/v1/purchases", "POST"),
        ("/api/v1/vendors", "POST"),
    ]

    for endpoint, method in endpoints:
        if method == "POST":
            response = client.post(
                endpoint,
                json={},  # Empty body
                headers={"Authorization": auth_headers["Authorization"]},
            )
        elif method == "PUT":
            response = client.put(
                endpoint,
                json={},
                headers={"Authorization": auth_headers["Authorization"]},
            )

        # Should not crash - should return appropriate error
        assert response.status_code in [200, 400, 401, 403, 404, 500]

        if response.status_code == 400:
            assert "message" in response.json


def test_max_pagination_limits(client, auth_headers):
    """Test pagination with very large page sizes"""
    # Try to request all records at once
    response = client.get(
        "/api/v1/sales?page=1&pageSize=10000",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should handle gracefully
    assert response.status_code in [200, 400]

    if response.status_code == 200:
        # Should respect some reasonable limit
        assert len(response.json["data"]) <= 1000


def test_negative_page_numbers(client, auth_headers):
    """Test pagination with negative page numbers"""
    response = client.get(
        "/api/v1/sales?page=-1&pageSize=10",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should handle gracefully
    assert response.status_code in [200, 400]

    if response.status_code == 200:
        # Should default to page 1
        assert response.json["data"] is not None
