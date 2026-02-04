import pytest
import uuid
from datetime import datetime
from app.models import Sale, Distributor, Wilaya, Zone, Region


def test_dashboard_stats_calculation(client, auth_headers, db):
    # Setup Hierarchy
    reg = Region(name="Reg_Dash")
    db.session.add(reg)
    db.session.flush()
    zn = Zone(name="Zn_Dash", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()
    wil = Wilaya(name="Wil_Dash", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()
    dist = Distributor(
        nom="Dist_Dash", wilaya_id=wil.id, supervisor_id=auth_headers["user_id"]
    )
    db.session.add(dist)
    db.session.flush()

    # Create 2 Sales: 1 Complete (1200 DA), 1 En Cours (800 DA)
    # The dashboard MUST only sum the 'complete' ones.
    s1 = Sale(
        date=datetime.now(),
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
        montant_total=1200.0,
    )
    s2 = Sale(
        date=datetime.now(),
        distributor_id=dist.id,
        supervisor_id=auth_headers["user_id"],
        status="en_cours",
        montant_total=800.0,
    )
    db.session.add_all([s1, s2])
    db.session.commit()

    response = client.get(
        "/api/v1/dashboard/stats",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200
    metrics = response.json["data"]["metrics"]
    # Total should be exactly 1200.0
    assert metrics["sales"] == 1200.0
