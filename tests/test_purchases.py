import pytest
import uuid
from decimal import Decimal
from app.models import Product, Distributor, Purchase, Inventory, Wilaya, Zone, Region


def test_create_purchase_lifecycle(client, auth_headers, db):
    # 1. Setup Hierarchy with unique codes
    reg = Region(name=f"Reg_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()
    zn = Zone(name=f"Zn_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()
    wil = Wilaya(name=f"Wil_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(
        nom="Dist Purchase", wilaya_id=wil.id, supervisor_id=auth_headers["user_id"]
    )
    db.session.add(dist)
    db.session.flush()

    unique_prod_code = f"P_PUR_{uuid.uuid4().hex[:6]}"
    prod = Product(
        code=unique_prod_code, designation="Test P", price_factory=Decimal("50.0")
    )
    db.session.add(prod)
    db.session.commit()

    # 2. Action: Create Purchase (Status Complete should trigger stock update)
    payload = {
        "distributeurId": dist.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [{"product_id": prod.id, "quantity": 100}],
    }
    resp = client.post(
        "/api/v1/purchases",
        json=payload,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 201
    purchase_id = resp.json["id"]

    # Verify stock increased
    inv = Inventory.query.filter_by(distributor_id=dist.id, product_id=prod.id).first()
    assert inv.stock_qte == 100

    # 3. Delete Purchase (Should revert/subtract the stock)
    client.delete(
        f"/api/v1/purchases/{purchase_id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    db.session.refresh(inv)
    assert inv.stock_qte == 0


# Add to /tests/test_purchases.py
def test_purchase_update_quantity_change(
    client, auth_headers, db, test_distributor, test_product
):
    """Test updating purchase with quantity changes"""
    from app.models import Purchase, PurchaseItem, Inventory
    from decimal import Decimal

    # 1. Create initial purchase (complete, affects inventory)
    purchase = Purchase(
        date="2026-02-03",
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
        montant_total=Decimal("5000.00"),
    )
    db.session.add(purchase)
    db.session.flush()

    item = PurchaseItem(
        purchase_id=purchase.id,
        product_id=test_product.id,
        quantity=100,
        unit_price=Decimal("50.00"),
    )
    db.session.add(item)
    db.session.commit()

    # Initialize inventory record
    inv = Inventory(
        distributor_id=test_distributor.id, product_id=test_product.id, stock_qte=0
    )
    db.session.add(inv)
    db.session.commit()

    # Apply purchase (should add 100 to inventory)
    from app.utils.inventory_sync import update_stock_incremental

    update_stock_incremental(test_distributor.id, test_product.id, 100)
    db.session.commit()

    db.session.refresh(inv)
    assert inv.stock_qte == 100

    # 2. Update purchase: increase quantity to 150
    update_data = {
        "date": "2026-02-03",
        "distributorId": test_distributor.id,
        "status": "complete",  # Still complete
        "products": [{"product_id": test_product.id, "quantity": 150}],
    }

    response = client.put(
        f"/api/v1/purchases/{purchase.id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200

    # Inventory should be: 100 (old) - 100 (removed) + 150 (added) = 150
    db.session.refresh(inv)
    assert inv.stock_qte == 150, f"Expected 150, got {inv.stock_qte}"

    # 3. Update purchase: decrease quantity to 75
    update_data["products"][0]["quantity"] = 75
    response = client.put(
        f"/api/v1/purchases/{purchase.id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200

    # Inventory should be: 150 - 150 + 75 = 75
    db.session.refresh(inv)
    assert inv.stock_qte == 75


def test_purchase_update_product_change(client, auth_headers, db, test_distributor):
    """Test updating purchase with different products"""
    from app.models import Purchase, PurchaseItem, Product, Inventory
    import uuid
    from decimal import Decimal

    # Create two products
    prod1 = Product(
        code=f"P_UPDATE1_{uuid.uuid4().hex[:4]}",
        designation="Product 1",
        price_factory=Decimal("50.0"),
    )
    prod2 = Product(
        code=f"P_UPDATE2_{uuid.uuid4().hex[:4]}",
        designation="Product 2",
        price_factory=Decimal("75.0"),
    )
    db.session.add_all([prod1, prod2])
    db.session.commit()

    # Initialize inventory
    inv1 = Inventory(
        distributor_id=test_distributor.id, product_id=prod1.id, stock_qte=0
    )
    inv2 = Inventory(
        distributor_id=test_distributor.id, product_id=prod2.id, stock_qte=0
    )
    db.session.add_all([inv1, inv2])
    db.session.commit()

    # 1. Create purchase with product 1
    purchase = Purchase(
        date="2026-02-03",
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
    )
    db.session.add(purchase)
    db.session.flush()

    item = PurchaseItem(
        purchase_id=purchase.id,
        product_id=prod1.id,
        quantity=50,
        unit_price=Decimal("50.00"),
    )
    db.session.add(item)
    db.session.commit()

    # Apply to inventory
    from app.utils.inventory_sync import update_stock_incremental

    update_stock_incremental(test_distributor.id, prod1.id, 50)
    db.session.commit()

    db.session.refresh(inv1)
    assert inv1.stock_qte == 50
    assert inv2.stock_qte == 0

    # 2. Update purchase: switch from product 1 to product 2
    update_data = {
        "date": "2026-02-03",
        "distributorId": test_distributor.id,
        "status": "complete",
        "products": [{"product_id": prod2.id, "quantity": 30}],
    }

    response = client.put(
        f"/api/v1/purchases/{purchase.id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200

    # Product 1 inventory should go back to 0, Product 2 should be 30
    db.session.refresh(inv1)
    db.session.refresh(inv2)
    assert inv1.stock_qte == 0, f"Product 1 should be 0, got {inv1.stock_qte}"
    assert inv2.stock_qte == 30, f"Product 2 should be 30, got {inv2.stock_qte}"


def test_purchase_update_status_and_quantity_simultaneously(
    client, auth_headers, db, test_distributor, test_product
):
    """Test updating both status and quantity at same time"""
    from app.models import Purchase, PurchaseItem, Inventory
    from decimal import Decimal

    # Initialize inventory
    inv = Inventory(
        distributor_id=test_distributor.id, product_id=test_product.id, stock_qte=200
    )
    db.session.add(inv)
    db.session.commit()

    # 1. Create purchase with status 'en_cours' (doesn't affect inventory)
    purchase = Purchase(
        date="2026-02-03",
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
        status="en_cours",
    )
    db.session.add(purchase)
    db.session.flush()

    item = PurchaseItem(
        purchase_id=purchase.id,
        product_id=test_product.id,
        quantity=100,
        unit_price=Decimal("50.00"),
    )
    db.session.add(item)
    db.session.commit()

    # Inventory should still be 200
    db.session.refresh(inv)
    assert inv.stock_qte == 200

    # 2. Update to 'complete' AND change quantity to 150
    update_data = {
        "date": "2026-02-03",
        "distributorId": test_distributor.id,
        "status": "complete",  # Changing status
        "products": [
            {"product_id": test_product.id, "quantity": 150}
        ],  # Changing quantity
    }

    response = client.put(
        f"/api/v1/purchases/{purchase.id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200

    # Inventory should be: 200 + 150 = 350
    # (was en_cours so no previous effect, now complete with 150)
    db.session.refresh(inv)
    assert inv.stock_qte == 350, f"Expected 350, got {inv.stock_qte}"

    # 3. Update to 'annule' and change quantity to 200
    update_data["status"] = "annule"
    update_data["products"][0]["quantity"] = 200

    response = client.put(
        f"/api/v1/purchases/{purchase.id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200

    # Inventory should be: 350 - 150 (remove complete) = 200
    # (annule doesn't add inventory, it removes previous complete effect)
    db.session.refresh(inv)
    assert inv.stock_qte == 200, f"Expected 200, got {inv.stock_qte}"


# Add to /tests/test_purchases.py
def test_delete_after_multiple_updates(
    client, auth_headers, db, test_distributor, test_product
):
    """Test delete after quantity changes restores original state"""
    from app.models import Purchase, PurchaseItem, Inventory
    from decimal import Decimal
    import uuid

    # Initial state
    initial_stock = 200
    inv = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=initial_stock,
    )
    db.session.add(inv)
    db.session.commit()

    # 1. Create purchase (complete, adds 100)
    purchase_data = {
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [{"product_id": test_product.id, "quantity": 100}],
    }

    resp = client.post(
        "/api/v1/purchases",
        json=purchase_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 201
    purchase_id = resp.json["id"]

    # Stock should be 300
    db.session.refresh(inv)
    assert inv.stock_qte == 300

    # 2. Update purchase: change quantity to 150
    update_data = {
        "date": "2026-02-03",
        "distributorId": test_distributor.id,
        "status": "complete",
        "products": [{"product_id": test_product.id, "quantity": 150}],
    }

    response = client.put(
        f"/api/v1/purchases/{purchase_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200

    # Stock should be: 300 - 100 + 150 = 350
    db.session.refresh(inv)
    assert inv.stock_qte == 350

    # 3. Update purchase: change quantity to 75
    update_data["products"][0]["quantity"] = 75
    response = client.put(
        f"/api/v1/purchases/{purchase_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200

    # Stock should be: 350 - 150 + 75 = 275
    db.session.refresh(inv)
    assert inv.stock_qte == 275

    # 4. Delete purchase
    response = client.delete(
        f"/api/v1/purchases/{purchase_id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200

    # CRITICAL: Should return to ORIGINAL stock (200), not intermediate state
    db.session.refresh(inv)
    assert inv.stock_qte == initial_stock, (
        f"Delete after updates failed! Expected {initial_stock}, got {inv.stock_qte}. "
        f"Delete should revert ALL changes, not just last update."
    )


def test_delete_after_status_transitions(
    client, auth_headers, db, test_distributor, test_product
):
    """Test delete after multiple status changes"""
    from app.models import Purchase, Inventory

    # Initial
    initial_stock = 100
    inv = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=initial_stock,
    )
    db.session.add(inv)
    db.session.commit()

    # 1. Create as 'en_cours' (no effect)
    purchase_data = {
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "en_cours",
        "products": [{"product_id": test_product.id, "quantity": 50}],
    }

    resp = client.post(
        "/api/v1/purchases",
        json=purchase_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    purchase_id = resp.json["id"]

    # Stock unchanged
    db.session.refresh(inv)
    assert inv.stock_qte == 100

    # 2. Update to 'complete' (adds 50)
    update_data = {
        "date": "2026-02-03",
        "distributorId": test_distributor.id,
        "status": "complete",
        "products": [{"product_id": test_product.id, "quantity": 50}],
    }

    client.put(
        f"/api/v1/purchases/{purchase_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Stock: 100 + 50 = 150
    db.session.refresh(inv)
    assert inv.stock_qte == 150

    # 3. Update to 'annule' (removes 50)
    update_data["status"] = "annule"
    client.put(
        f"/api/v1/purchases/{purchase_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Stock: 150 - 50 = 100 (back to original)
    db.session.refresh(inv)
    assert inv.stock_qte == 100

    # 4. Update back to 'complete' with different quantity 30
    update_data["status"] = "complete"
    update_data["products"][0]["quantity"] = 30
    client.put(
        f"/api/v1/purchases/{purchase_id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Stock: 100 + 30 = 130
    db.session.refresh(inv)
    assert inv.stock_qte == 130

    # 5. DELETE - should return to original 100
    client.delete(
        f"/api/v1/purchases/{purchase_id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    db.session.refresh(inv)
    assert (
        inv.stock_qte == initial_stock
    ), f"Complex status transition delete failed. Expected {initial_stock}, got {inv.stock_qte}"
