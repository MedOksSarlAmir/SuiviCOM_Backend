import pytest
import uuid
from app.models import Product, Distributor, Wilaya, Zone, Region, Inventory
from app.utils.inventory_sync import update_stock_incremental


def test_manual_stock_adjustment(client, auth_headers, db):
    # 1. Setup Hierarchy
    reg = Region(name=f"Reg_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()
    zn = Zone(name=f"Zn_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()
    wil = Wilaya(name=f"Wil_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    # Ensure Distributor is owned by the current test supervisor
    dist = Distributor(
        nom="D_INV_ADJ", wilaya_id=wil.id, supervisor_id=auth_headers["user_id"]
    )
    db.session.add(dist)
    db.session.flush()

    # Unique product code
    unique_code = f"P_ADJ_{uuid.uuid4().hex[:6]}"
    prod = Product(code=unique_code, designation="Adj Prod")
    db.session.add(prod)
    db.session.commit()

    # 2. Action: Adjust stock by +50
    payload = {
        "distributor_id": dist.id,
        "quantity": 50,
        "note": "Initial inventory count",
    }
    response = client.post(
        f"/api/v1/inventory/adjust/{prod.id}",
        json=payload,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # If this is still 500, we will check the logs, but this setup is now correct
    assert response.status_code == 201

    # 3. Verification: Check inventory table
    inv = Inventory.query.filter_by(distributor_id=dist.id, product_id=prod.id).first()
    assert inv.stock_qte == 50

    # 4. Verification: Check History View
    hist_resp = client.get(
        f"/api/v1/inventory/history/{dist.id}/{prod.id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert hist_resp.status_code == 200
    assert len(hist_resp.json["data"]) > 0
    assert hist_resp.json["data"][0]["type"] == "DECALAGE"
