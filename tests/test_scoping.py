from urllib import response
import uuid
from app.models import Vendor, User


def test_supervisor_cannot_see_others_vendors(client, auth_headers, db):
    # 1. Create another supervisor and a vendor for them
    other_sup = User(
        username=f"other_{uuid.uuid4().hex[:4]}",
        password_hash="...",
        role="superviseur",
    )
    db.session.add(other_sup)
    db.session.flush()

    # Added unique code to avoid IntegrityError
    secret_vendor = Vendor(
        nom="Secret", code=f"CODE_{uuid.uuid4().hex[:4]}", supervisor_id=other_sup.id
    )
    db.session.add(secret_vendor)
    db.session.commit()

    response = client.get(
        "/api/v1/vendors", headers={"Authorization": auth_headers["Authorization"]}
    )

    vendor_names = [v["nom"] for v in response.json]
    assert "Secret" not in vendor_names


def test_supervisor_cannot_see_others_distributors(client, auth_headers, db):
    """Test Supervisor A cannot see Supervisor B's distributors"""
    # 1. Create another supervisor
    from app.models import User, Distributor, Wilaya, Zone, Region
    import uuid

    other_sup = User(
        username=f"other_{uuid.uuid4().hex[:8]}",
        password_hash="...",
        role="superviseur",
        nom="Other",
        prenom="Supervisor",
    )
    db.session.add(other_sup)
    db.session.flush()

    # 2. Create hierarchy for other supervisor
    reg = Region(name=f"Reg_Other_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_Other_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_Other_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    # 3. Create distributor for other supervisor
    other_dist = Distributor(
        nom="Secret Distributor", wilaya_id=wil.id, supervisor_id=other_sup.id
    )
    db.session.add(other_dist)
    db.session.commit()

    # 4. Test that current supervisor CANNOT see other's distributor
    response = client.get("/api/v1/supervisor/distributors", headers=auth_headers)
    assert response.status_code == 200
    # FIX: response.json is a direct list [], not a dict
    distributor_names = [d["nom"] for d in response.json]
    assert "Secret Distributor" not in distributor_names


def test_supervisor_cannot_see_others_sales(client, auth_headers, db):
    """Test Supervisor A cannot see Supervisor B's sales"""
    from app.models import User, Sale, Distributor, Vendor, Wilaya, Zone, Region
    import uuid
    from datetime import datetime

    # Create other supervisor and full hierarchy
    other_sup = User(
        username=f"other_sale_{uuid.uuid4().hex[:8]}",
        password_hash="...",
        role="superviseur",
    )
    db.session.add(other_sup)
    db.session.flush()

    # Full hierarchy
    reg = Region(name=f"Reg_S_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_S_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_S_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(
        nom=f"Dist_S_{uuid.uuid4().hex[:4]}",
        wilaya_id=wil.id,
        supervisor_id=other_sup.id,
    )
    db.session.add(dist)
    db.session.flush()

    vend = Vendor(
        nom="V_Sale",
        code=f"V_S_{uuid.uuid4().hex[:4]}",
        distributor_id=dist.id,
        supervisor_id=other_sup.id,
    )
    db.session.add(vend)
    db.session.flush()

    # Create sale for other supervisor
    secret_sale = Sale(
        date=datetime.now(),
        distributor_id=dist.id,
        vendor_id=vend.id,
        supervisor_id=other_sup.id,
        status="complete",
        montant_total=1000.0,
    )
    db.session.add(secret_sale)
    db.session.commit()

    # Test current supervisor's sales endpoint
    response = client.get(
        "/api/v1/sales",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200
    sales_data = response.json.get("data", [])

    # Should not find the other supervisor's sale
    other_sale_ids = [s["id"] for s in sales_data if s.get("id") == secret_sale.id]
    assert (
        len(other_sale_ids) == 0
    ), f"Data leakage! Found other supervisor's sale: {other_sale_ids}"


def test_supervisor_cannot_access_others_inventory(client, auth_headers, db):
    """Test Supervisor A cannot access Supervisor B's inventory"""
    from app.models import User, Inventory, Distributor, Product, Wilaya, Zone, Region
    import uuid

    # Create other supervisor with inventory
    other_sup = User(
        username=f"other_inv_{uuid.uuid4().hex[:8]}",
        password_hash="...",
        role="superviseur",
    )
    db.session.add(other_sup)
    db.session.flush()

    # Hierarchy
    reg = Region(name=f"Reg_I_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_I_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_I_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(
        nom="Secret Inventory Dist", wilaya_id=wil.id, supervisor_id=other_sup.id
    )
    db.session.add(dist)
    db.session.flush()

    prod = Product(
        code=f"P_SECRET_{uuid.uuid4().hex[:4]}", name="Secret Product"
    )
    db.session.add(prod)
    db.session.flush()

    # Create inventory for other supervisor
    secret_inv = Inventory(distributor_id=dist.id, product_id=prod.id, stock_qte=500)
    db.session.add(secret_inv)
    db.session.commit()

    # Try to access other supervisor's inventory via API
    response = client.get(
        f"/api/v1/inventory/{dist.id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should either return empty or 403/404
    if response.status_code == 200:
        # If returns data, check it doesn't contain other supervisor's inventory
        inventory_items = response.json.get("data", [])
        secret_items = [
            item
            for item in inventory_items
            if item.get("product_id") == prod.id
            or item.get("distributor_id") == dist.id
        ]
        assert len(secret_items) == 0, "Data leakage in inventory endpoint"
