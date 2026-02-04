# New file: /tests/test_security/test_permission_escalation.py
import pytest
import uuid
import json


def test_supervisor_update_others_sale_by_id_guessing(client, auth_headers, db, app):
    """Test supervisor trying to update another supervisor's sale"""
    from app.models import User, Sale, Distributor, Vendor, Wilaya, Zone, Region
    from app.extensions import bcrypt

    # Create another supervisor
    other_sup = User(
        username=f"other_attack_{uuid.uuid4().hex[:8]}",
        password_hash=bcrypt.generate_password_hash("password").decode("utf-8"),
        role="superviseur",
        nom="Other",
        prenom="Supervisor",
    )
    db.session.add(other_sup)
    db.session.flush()

    # Create hierarchy for other supervisor
    reg = Region(name=f"Reg_Att_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_Att_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_Att_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(
        nom=f"Dist_Att_{uuid.uuid4().hex[:4]}",
        wilaya_id=wil.id,
        supervisor_id=other_sup.id,
    )
    db.session.add(dist)
    db.session.flush()

    vendor = Vendor(
        nom="V_Attack",
        code=f"V_ATT_{uuid.uuid4().hex[:4]}",
        distributor_id=dist.id,
        supervisor_id=other_sup.id,
    )
    db.session.add(vendor)
    db.session.flush()

    # Create sale for other supervisor
    other_sale = Sale(
        date="2026-02-03",
        distributor_id=dist.id,
        vendor_id=vendor.id,
        supervisor_id=other_sup.id,
        status="complete",
        montant_total=1000.0,
    )
    db.session.add(other_sale)
    db.session.commit()

    # Try to update other supervisor's sale (ID guessing attack)
    update_data = {
        "date": "2026-02-04",  # Trying to change date
        "status": "annule",
        "distributorId": dist.id,
        "vendorId": vendor.id,
        "products": [],
    }

    response = client.put(
        f"/api/v1/sales/{other_sale.id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should FAIL with 403 or 404
    assert response.status_code in [
        403,
        404,
    ], f"Permission escalation successful! Got {response.status_code}"

    if response.status_code == 403:
        assert (
            "accès" in response.json.get("message", "").lower()
            or "interdit" in response.json.get("message", "").lower()
        )

    # Verify sale wasn't changed
    db.session.refresh(other_sale)
    assert other_sale.date.strftime("%Y-%m-%d") == "2026-02-03"
    assert other_sale.status == "complete"


def test_supervisor_modify_others_inventory_directly(client, auth_headers, db):
    """Test supervisor trying to modify another supervisor's inventory"""
    from app.models import User, Inventory, Distributor, Product, Wilaya, Zone, Region
    from app.extensions import bcrypt

    # Create other supervisor
    other_sup = User(
        username=f"other_inv_attack_{uuid.uuid4().hex[:8]}",
        password_hash=bcrypt.generate_password_hash("password").decode("utf-8"),
        role="superviseur",
    )
    db.session.add(other_sup)
    db.session.flush()

    # Create hierarchy and inventory for other supervisor
    reg = Region(name=f"Reg_InvAtt_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_InvAtt_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_InvAtt_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(
        nom="Dist_Inv_Attack", wilaya_id=wil.id, supervisor_id=other_sup.id
    )
    db.session.add(dist)
    db.session.flush()

    prod = Product(
        code=f"P_INVATT_{uuid.uuid4().hex[:4]}", designation="Attack Product"
    )
    db.session.add(prod)
    db.session.flush()

    # Create inventory for other supervisor
    other_inv = Inventory(distributor_id=dist.id, product_id=prod.id, stock_qte=500)
    db.session.add(other_inv)
    db.session.commit()

    # Try to adjust other supervisor's inventory directly
    payload = {
        "distributor_id": dist.id,
        "quantity": -100,  # Trying to reduce their stock
        "note": "Malicious adjustment",
    }

    response = client.post(
        f"/api/v1/inventory/adjust/{prod.id}",
        json=payload,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should FAIL with 403 or 404
    assert response.status_code in [
        403,
        404,
        400,
    ], f"Permission escalation on inventory! Got {response.status_code}"

    # Verify inventory unchanged
    db.session.refresh(other_inv)
    assert other_inv.stock_qte == 500


def test_supervisor_create_sale_for_others_distributor(client, auth_headers, db):
    """Test supervisor trying to create sale for distributor they don't own"""
    from app.models import User, Distributor, Vendor, Wilaya, Zone, Region
    from app.extensions import bcrypt

    # Create other supervisor and their distributor
    other_sup = User(
        username=f"other_salecreate_{uuid.uuid4().hex[:8]}",
        password_hash=bcrypt.generate_password_hash("password").decode("utf-8"),
        role="superviseur",
    )
    db.session.add(other_sup)
    db.session.flush()

    reg = Region(name=f"Reg_SC_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zn_SC_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wil_SC_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    other_dist = Distributor(
        nom="Not My Distributor", wilaya_id=wil.id, supervisor_id=other_sup.id
    )
    db.session.add(other_dist)
    db.session.flush()

    other_vendor = Vendor(
        nom="Not My Vendor",
        code=f"V_SC_{uuid.uuid4().hex[:4]}",
        distributor_id=other_dist.id,
        supervisor_id=other_sup.id,
    )
    db.session.add(other_vendor)

    # Create a product
    from app.models import Product

    prod = Product(code=f"P_SC_{uuid.uuid4().hex[:4]}", designation="Test Product")
    db.session.add(prod)
    db.session.commit()

    # Try to create sale for other supervisor's distributor
    sale_data = {
        "acteurId": other_vendor.id,
        "distributeurId": other_dist.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [{"product_id": prod.id, "quantity": 10}],
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should FAIL - cannot create sale for distributor you don't own
    assert response.status_code in [
        403,
        404,
        400,
    ], f"Created sale for other supervisor's distributor! Got {response.status_code}"


def test_admin_privilege_escalation_attempt(client, auth_headers, db):
    """Test supervisor trying to elevate privileges to admin"""
    # Supervisor trying to update their own role
    update_data = {"role": "admin"}  # Trying to self-promote

    response = client.put(
        f"/api/v1/users/{auth_headers['user_id']}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should FAIL with 403
    assert response.status_code == 403, "Role escalation successful!"

    # Try to create a user with admin role
    user_data = {
        "username": f"fake_admin_{uuid.uuid4().hex[:4]}",
        "password": "password123",
        "role": "admin",  # Supervisor trying to create admin
        "nom": "Fake",
        "prenom": "Admin",
    }

    response = client.post(
        "/api/v1/users",
        json=user_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should FAIL or create with downgraded role
    if response.status_code == 201:
        # Check if role was downgraded
        user_id = response.json.get("id")
        from app.models import User

        created_user = User.query.get(user_id)
        assert created_user.role != "admin", "Supervisor created admin user!"
    else:
        assert response.status_code in [403, 400]


def test_cross_supervisor_data_access_via_foreign_keys(client, auth_headers, db):
    """Test accessing other supervisor's data through foreign key relationships"""
    from app.models import User, Sale, Distributor, Vendor
    from app.extensions import bcrypt

    # Create two supervisors with data
    sup1 = User(
        username=f"sup1_fk_{uuid.uuid4().hex[:8]}",
        password_hash="hash1",
        role="superviseur",
    )

    sup2 = User(
        username=f"sup2_fk_{uuid.uuid4().hex[:8]}",
        password_hash="hash2",
        role="superviseur",
    )
    db.session.add_all([sup1, sup2])
    db.session.flush()

    # Sup1 creates distributor and vendor
    from app.models import Wilaya, Zone, Region

    reg = Region(name=f"Reg_FK_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session
