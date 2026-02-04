import pytest
import uuid
from app.models import Vendor, Visit, Distributor, Wilaya, Zone, Region


def test_visit_upsert_logic(client, auth_headers, db):
    # Setup
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

    # Use UUID for vendor code to avoid IntegrityError
    unique_v_code = f"V_{uuid.uuid4().hex[:6]}"
    vend = Vendor(
        nom="V1",
        code=unique_v_code,
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(vend)
    db.session.commit()

    target_date = "2026-02-03"

    # Step 1: Upsert Programmed Visits
    client.post(
        "/api/v1/visits/upsert",
        json={"vendor_id": vend.id, "date": target_date, "field": "prog", "value": 10},
        headers={"Authorization": auth_headers["Authorization"]},
    )

    visit = Visit.query.filter_by(vendor_id=vend.id, date=target_date).first()
    assert visit.visites_programmees == 10
    assert "non effectuée" in visit.status

    # Step 2: Upsert Performed Visits (Should change status to 'effectuée')
    client.post(
        "/api/v1/visits/upsert",
        json={"vendor_id": vend.id, "date": target_date, "field": "done", "value": 1},
        headers={"Authorization": auth_headers["Authorization"]},
    )

    db.session.refresh(visit)
    assert visit.visites_effectuees == 1
    assert visit.status == "effectuée"
