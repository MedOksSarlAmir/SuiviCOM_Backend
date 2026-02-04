import pytest
import uuid
from app.models import Vendor, Distributor, Wilaya, Zone, Region, Sale


def test_vendor_deletion_protection(client, auth_headers, db):
    # 1. Setup Vendor
    reg = Region(name="R_V")
    db.session.add(reg)
    db.session.flush()
    zn = Zone(name="Z_V", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()
    wil = Wilaya(name="W_V", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()
    dist = Distributor(
        nom="D_V", wilaya_id=wil.id, supervisor_id=auth_headers["user_id"]
    )
    db.session.add(dist)
    db.session.flush()

    vend = Vendor(
        nom="V_Del",
        code=f"C_{uuid.uuid4().hex[:4]}",
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(vend)
    db.session.flush()

    # 2. Add a Sale for this vendor
    sale = Sale(
        date="2026-02-03",
        distributor_id=dist.id,
        vendor_id=vend.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(sale)
    db.session.commit()

    # 3. Action: Try to delete the vendor
    response = client.delete(
        f"/api/v1/vendors/{vend.id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # 4. Verification: Should fail with 400 because vendor has history
    assert response.status_code == 400
    assert "Impossible de supprimer" in response.json["message"]
