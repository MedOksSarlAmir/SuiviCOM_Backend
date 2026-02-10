import pytest
from app.utils.inventory_sync import update_stock_incremental  # Import fixed
from app.models import Inventory, Product, Distributor, Wilaya, Zone, Region
import uuid 

def test_stock_incremental_update(app, db):
    # 1. Create full hierarchy for foreign keys
    reg = Region(name="North")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name="Center", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name="Alger", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    dist = Distributor(nom="Dist 1", wilaya_id=wil.id)
    prod = Product(code=f"P_{uuid.uuid4().hex[:4]}", name="Test Prod")
    db.session.add_all([dist, prod])
    db.session.commit()

    update_stock_incremental(dist.id, prod.id, 10)
    db.session.commit()

    inv = Inventory.query.filter_by(distributor_id=dist.id, product_id=prod.id).first()
    assert inv.stock_qte == 10
