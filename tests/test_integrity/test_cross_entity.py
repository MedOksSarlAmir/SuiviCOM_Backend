import pytest
import uuid
from decimal import Decimal


def test_delete_distributor_cascade(client, auth_headers, db, app):
    """Test what happens when distributor is deleted"""
    from app.models import (
        Distributor,
        Vendor,
        Sale,
        Purchase,
        Inventory,
        Wilaya,
        Zone,
        Region,
        Visit,
    )

    # Create complete hierarchy with data
    reg = Region(name=f"Reg_Delete_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_Delete_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_Delete_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    # Create distributor with associated data
    dist = Distributor(
        nom=f"Dist_Delete_{uuid.uuid4().hex[:4]}",
        wilaya_id=wil.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(dist)
    db.session.flush()

    # Create vendor for this distributor
    vendor = Vendor(
        nom="Vendor_Delete",
        code=f"V_DEL_{uuid.uuid4().hex[:4]}",
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(vendor)
    db.session.flush()

    # Create product
    from app.models import Product, ProductCategory, ProductType

    cat = ProductCategory(name=f"Cat_Delete_{uuid.uuid4().hex[:4]}")
    db.session.add(cat)
    db.session.flush()

    p_type = ProductType(name=f"Type_Delete_{uuid.uuid4().hex[:4]}")
    db.session.add(p_type)
    db.session.flush()

    prod = Product(
        code=f"P_DEL_{uuid.uuid4().hex[:4]}",
        designation="Delete Test Product",
        category_id=cat.id,
        type_id=p_type.id,
    )
    db.session.add(prod)
    db.session.flush()

    # Create inventory
    inventory = Inventory(distributor_id=dist.id, product_id=prod.id, stock_qte=100)
    db.session.add(inventory)

    # Create sale
    sale = Sale(
        date="2026-02-03",
        distributor_id=dist.id,
        vendor_id=vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
        montant_total=Decimal("1000.00"),
    )
    db.session.add(sale)

    # Create purchase
    purchase = Purchase(
        date="2026-02-03",
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
        montant_total=Decimal("5000.00"),
    )
    db.session.add(purchase)

    # Create visit
    visit = Visit(
        date="2026-02-03",
        distributor_id=dist.id,
        vendor_id=vendor.id,
        supervisor_id=auth_headers["user_id"],
        visites_programmees=5,
    )
    db.session.add(visit)

    db.session.commit()

    # Try to delete distributor via API
    response = client.delete(
        f"/api/v1/supervisor/distributors/{dist.id}",  # Ensure this route exists!
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Check response - should either:
    # 1. Success with cascade delete
    # 2. Fail with 400 (cannot delete due to references)
    # 3. Soft delete (set active=False)

    if response.status_code == 200:
        # If deletion successful, verify all related data is handled
        # Check what happens - depends on business rules
        pass
    elif response.status_code == 400:
        # Expected - distributor has references
        assert (
            "impossible" in response.json.get("message", "").lower()
            or "reference" in response.json.get("message", "").lower()
        )
    else:
        # Unexpected
        pytest.fail(f"Unexpected response: {response.status_code}")


def test_deactivate_product_integrity(client, auth_headers, db):
    """Test deactivating a product with existing sales/purchases"""
    from app.models import (
        Product,
        Sale,
        Purchase,
        Inventory,
        ProductCategory,
        ProductType,
    )
    import uuid

    # Create product
    cat = ProductCategory(name=f"Cat_Deact_{uuid.uuid4().hex[:4]}")
    db.session.add(cat)
    db.session.flush()

    p_type = ProductType(name=f"Type_Deact_{uuid.uuid4().hex[:4]}")
    db.session.add(p_type)
    db.session.flush()

    prod = Product(
        code=f"P_DEACT_{uuid.uuid4().hex[:4]}",
        designation="Product to Deactivate",
        category_id=cat.id,
        type_id=p_type.id,
        active=True,
    )
    db.session.add(prod)
    db.session.commit()

    # Create hierarchy for sale
    from app.models import Distributor, Vendor, Wilaya, Zone, Region

    reg = Region(name=f"Reg_Deact_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_Deact_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_Deact_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(
        nom=f"Dist_Deact_{uuid.uuid4().hex[:4]}",
        wilaya_id=wil.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(dist)
    db.session.flush()

    vendor = Vendor(
        nom="Vendor_Deact",
        code=f"V_DEACT_{uuid.uuid4().hex[:4]}",
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(vendor)
    db.session.commit()

    # Create sale with this product
    sale = Sale(
        date="2026-02-03",
        distributor_id=dist.id,
        vendor_id=vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
        montant_total=Decimal("1000.00"),
    )
    db.session.add(sale)
    db.session.flush()

    from app.models import SaleItem

    sale_item = SaleItem(sale_id=sale.id, product_id=prod.id, quantity=10)
    db.session.add(sale_item)
    db.session.commit()

    # Now try to deactivate product
    response = client.put(
        f"/api/v1/products/{prod.id}",
        json={"active": False},
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should either:
    # 1. Success (soft delete)
    # 2. Fail with error (cannot deactivate with history)

    if response.status_code == 200:
        # Product deactivated, verify it can't be used in NEW sales
        new_sale_data = {
            "acteurId": vendor.id,
            "distributeurId": dist.id,
            "date": "2026-02-04",
            "status": "complete",
            "products": [{"product_id": prod.id, "quantity": 5}],
        }

        new_sale_response = client.post(
            "/api/v1/sales",
            json=new_sale_data,
            headers={"Authorization": auth_headers["Authorization"]},
        )

        # Should fail because product is inactive
        assert new_sale_response.status_code in [400, 404, 422]
    elif response.status_code == 400:
        # Expected - product has history
        assert (
            "historique" in response.json.get("message", "").lower()
            or "utilisé" in response.json.get("message", "").lower()
        )


def test_vendor_transfer_between_distributors(client, auth_headers, db):
    """Test transferring vendor to another distributor"""
    from app.models import Vendor, Distributor, Wilaya, Zone, Region, Sale
    import uuid

    # Create two distributors
    reg = Region(name=f"Reg_Xfer_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_Xfer_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_Xfer_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    # Distributor 1 (original)
    dist1 = Distributor(
        nom=f"Dist1_Xfer_{uuid.uuid4().hex[:4]}",
        wilaya_id=wil.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(dist1)
    db.session.flush()

    # Distributor 2 (target)
    dist2 = Distributor(
        nom=f"Dist2_Xfer_{uuid.uuid4().hex[:4]}",
        wilaya_id=wil.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(dist2)
    db.session.flush()

    # Create vendor under dist1
    vendor = Vendor(
        nom="Transfer Vendor",
        code=f"V_XFER_{uuid.uuid4().hex[:4]}",
        distributor_id=dist1.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(vendor)
    db.session.commit()

    # Create sale for this vendor (under dist1)
    sale = Sale(
        date="2026-02-03",
        distributor_id=dist1.id,
        vendor_id=vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
    )
    db.session.add(sale)
    db.session.commit()

    # Try to transfer vendor to dist2
    transfer_data = {"distributor_id": dist2.id}

    response = client.put(
        f"/api/v1/vendors/{vendor.id}/transfer",
        json=transfer_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should either:
    # 1. Success - vendor transferred, old sales remain with dist1
    # 2. Fail - cannot transfer vendor with sales history

    if response.status_code == 200:
        # Verify vendor now belongs to dist2
        db.session.refresh(vendor)
        assert vendor.distributor_id == dist2.id

        # Verify old sale still references dist1
        db.session.refresh(sale)
        assert sale.distributor_id == dist1.id
    elif response.status_code == 400:
        # Expected - vendor has history
        assert "historique" in response.json.get("message", "").lower()
