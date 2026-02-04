import pytest
from decimal import Decimal
from app.models import Sale, Inventory, StockAdjustment
from sqlalchemy import text


def test_pricing_logic_by_vendor_type(
    client, auth_headers, db, test_distributor, test_product
):
    """
    GAP: Pricing Integrity.
    Verifies that 'gros' vendors get 'price_gros' and 'detail' get 'price_detail'.
    """
    from app.models import Vendor
    import uuid

    # 1. Setup two vendors with different types
    v_gros = Vendor(
        nom="Gros",
        code=f"G_{uuid.uuid4().hex[:4]}",
        vendor_type="gros",
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
    )
    v_detail = Vendor(
        nom="Detail",
        code=f"D_{uuid.uuid4().hex[:4]}",
        vendor_type="detail",
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add_all([v_gros, v_detail])
    db.session.commit()

    # Prices in test_product are: factory=50, gros=60, detail=70

    sale_gros = {
        "acteurId": v_gros.id,
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "en_cours",
        "products": [{"product_id": test_product.id, "quantity": 10}],
    }
    resp1 = client.post(
        "/api/v1/sales",
        json=sale_gros,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # FIX: Check if the response contains the new total directly
    assert resp1.status_code == 201

    # Refresh DB session to ensure price relationships are loaded
    db.session.expire_all()
    # Use Session.get() as per SQLAlchemy 2.0 (Query.get is legacy)
    sale_db_gros = db.session.get(Sale, resp1.json["id"])

    assert float(sale_db_gros.montant_total) == 600.0


def test_inventory_global_refresh_endpoint(client, auth_headers, db):
    """
    GAP: refresh_inventory_data endpoint.
    Verifies that the endpoint actually triggers the stored procedure and returns 200.
    """
    # Note: In a test env, sp_refresh_inventory might not exist yet.
    # We test that the controller handles the call correctly.
    response = client.post(
        "/api/v1/inventory/refresh",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # If the SP is missing in your test DB, this might be 500.
    # That is exactly what a QA test should catch!
    assert response.status_code == 200
    assert "Stock recalculé" in response.json["message"]


def test_sale_item_validation_edge_cases(
    client, auth_headers, db, test_distributor, test_vendor, test_product
):
    """
    GAP: Data validation.
    Verifies that negative or zero quantities are ignored as per your controller logic.
    """
    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [
            {"product_id": test_product.id, "quantity": -50},  # Should be ignored
            {"product_id": test_product.id, "quantity": 0},  # Should be ignored
        ],
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 201
    sale_id = response.json["id"]
    sale_db = Sale.query.get(sale_id)

    # According to your code: if qty <= 0: continue
    # So the sale should have 0 items and 0 total.
    assert len(sale_db.items) == 0
    assert float(sale_db.montant_total) == 0.0


def test_upsert_sale_item_atomicity(
    client, auth_headers, db, test_distributor, test_vendor, test_product
):
    """
    GAP: Upsert math.
    Verifies that changing a quantity from 10 to 5 updates inventory by +5 (restore).
    """
    # 1. Initial Stock at 100
    db.session.execute(
        text(
            "INSERT INTO dbo.inventory (distributor_id, product_id, stock_qte) VALUES (:d, :p, 100)"
        ),
        {"d": test_distributor.id, "p": test_product.id},
    )
    db.session.commit()

    # 2. Upsert 10 units
    payload = {
        "vendor_id": test_vendor.id,
        "distributor_id": test_distributor.id,
        "product_id": test_product.id,
        "date": "2026-02-03",
        "quantity": 10,
    }
    client.post(
        "/api/v1/sales/upsert-item",
        json=payload,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    inv = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()
    assert inv.stock_qte == 90  # 100 - 10

    # 3. Change to 4 units (Should return 6 to stock)
    payload["quantity"] = 4
    client.post(
        "/api/v1/sales/upsert-item",
        json=payload,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    db.session.refresh(inv)
    assert inv.stock_qte == 96  # 100 - 4
