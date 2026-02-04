import pytest
import uuid
from decimal import Decimal
from app.models import (
    Product,
    Distributor,
    Vendor,
    Sale,
    Inventory,
    Wilaya,
    Zone,
    Region,
)


def test_create_sale_integration(client, auth_headers, db):
    # 1. Setup dependencies
    reg = Region(name="Reg_Sale")
    db.session.add(reg)
    db.session.flush()
    zn = Zone(name="Zn_Sale", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()
    wil = Wilaya(name="Wil_Sale", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(nom="Dist Test", active=True, wilaya_id=wil.id)
    db.session.add(dist)
    db.session.flush()

    # Generate a unique code to avoid IntegrityError
    unique_prod_code = f"P_{uuid.uuid4().hex[:6]}"
    prod = Product(
        code=unique_prod_code,
        designation="Prod Test",
        price_detail=Decimal("100.00"),
        active=True,
    )
    db.session.add(prod)
    db.session.flush()

    unique_vend_code = f"V_{uuid.uuid4().hex[:6]}"
    vend = Vendor(
        nom="V1",
        prenom="T",
        code=unique_vend_code,
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
        active=True,
    )
    db.session.add(vend)
    db.session.commit()

    # 2. Action
    sale_data = {
        "acteurId": vend.id,
        "distributeurId": dist.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [{"product_id": prod.id, "quantity": 10}],
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # 3. Verification
    assert response.status_code == 201


# Add to /tests/test_sales.py
def test_sale_status_transition_inventory_impact(
    client, auth_headers, db, test_distributor, test_vendor, test_product
):
    """Test that inventory updates when sale status changes to/from complete"""
    # 1. Create sale with status 'en_cours' (should NOT affect inventory)
    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "en_cours",
        "products": [{"product_id": test_product.id, "quantity": 10}],
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 201
    sale_id = response.json["id"]

    # Verify inventory NOT changed (en_cours shouldn't affect stock)
    inv = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()
    initial_stock = inv.stock_qte if inv else 0

    # 2. Update sale to 'complete' (SHOULD reduce inventory)
    update_data = {
        "status": "complete",
        "date": "2026-02-03",
        "distributorId": test_distributor.id,
        "vendorId": test_vendor.id,
        "products": [{"product_id": test_product.id, "quantity": 10}],
    }

    response = client.put(
        f"/api/v1/sales/{sale_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200

    # Verify inventory reduced by 10
    db.session.refresh(inv) if inv else None
    new_stock = inv.stock_qte if inv else 0
    assert new_stock == initial_stock - 10  # Stock should decrease

    # 3. Update back to 'en_cours' (SHOULD restore inventory)
    update_data["status"] = "en_cours"
    response = client.put(
        f"/api/v1/sales/{sale_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200

    # Verify inventory restored
    db.session.refresh(inv) if inv else None
    final_stock = inv.stock_qte if inv else 0
    assert final_stock == initial_stock  # Back to original


# Add to /tests/test_purchases.py
def test_purchase_status_transition_inventory_impact(
    client, auth_headers, db, test_distributor, test_product
):
    """Test that inventory updates when purchase status changes to/from complete"""
    # 1. Create purchase with status 'en_cours'
    payload = {
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "en_cours",
        "products": [{"product_id": test_product.id, "quantity": 50}],
    }

    resp = client.post(
        "/api/v1/purchases",
        json=payload,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 201
    purchase_id = resp.json["id"]

    # Inventory should NOT be affected
    inv = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()
    initial_stock = inv.stock_qte if inv else 0

    # 2. Update to 'complete' (SHOULD increase inventory)
    update_data = {
        "status": "complete",
        "date": "2026-02-03",
        "distributorId": test_distributor.id,
        "products": [{"product_id": test_product.id, "quantity": 50}],
    }

    response = client.put(
        f"/api/v1/purchases/{purchase_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200

    # Verify inventory increased
    db.session.refresh(inv) if inv else None
    new_stock = inv.stock_qte if inv else 0
    assert new_stock == initial_stock + 50

    # 3. Update to 'annule' (SHOULD decrease inventory if was complete)
    update_data["status"] = "annule"
    response = client.put(
        f"/api/v1/purchases/{purchase_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200

    # Verify inventory restored
    db.session.refresh(inv) if inv else None
    final_stock = inv.stock_qte if inv else 0
    assert final_stock == initial_stock
