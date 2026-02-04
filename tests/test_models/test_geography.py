import pytest
from app.models import Region, Zone, Wilaya


def test_region_creation(db):
    """Test Region model creation"""
    region = Region(name="North Region")
    db.session.add(region)
    db.session.commit()

    assert region.id is not None
    assert region.name == "North Region"
    assert len(region.zones) == 0


def test_zone_creation(db):
    """Test Zone model creation with region relationship"""
    region = Region(name="Test Region")
    db.session.add(region)
    db.session.flush()

    zone = Zone(name="Central Zone", region_id=region.id)
    db.session.add(zone)
    db.session.commit()

    assert zone.id is not None
    assert zone.region == region
    assert zone.region_id == region.id
    assert len(zone.wilayas) == 0


def test_wilaya_creation(db):
    """Test Wilaya model creation with zone relationship"""
    region = Region(name="Test Region")
    db.session.add(region)
    db.session.flush()

    zone = Zone(name="Test Zone", region_id=region.id)
    db.session.add(zone)
    db.session.flush()

    wilaya = Wilaya(name="Algiers", zone_id=zone.id)
    db.session.add(wilaya)
    db.session.commit()

    assert wilaya.id is not None
    assert wilaya.zone == zone
    assert wilaya.zone_id == zone.id


def test_region_zones_relationship(db):
    """Test Region -> Zone relationship"""
    region = Region(name="Test Region")
    db.session.add(region)
    db.session.flush()

    zone1 = Zone(name="Zone 1", region_id=region.id)
    zone2 = Zone(name="Zone 2", region_id=region.id)
    db.session.add_all([zone1, zone2])
    db.session.commit()

    assert len(region.zones) == 2
    assert zone1 in region.zones
    assert zone2 in region.zones


def test_zone_wilayas_relationship(db):
    """Test Zone -> Wilaya relationship"""
    region = Region(name="Test Region")
    db.session.add(region)
    db.session.flush()

    zone = Zone(name="Test Zone", region_id=region.id)
    db.session.add(zone)
    db.session.flush()

    wilaya1 = Wilaya(name="Wilaya 1", zone_id=zone.id)
    wilaya2 = Wilaya(name="Wilaya 2", zone_id=zone.id)
    db.session.add_all([wilaya1, wilaya2])
    db.session.commit()

    assert len(zone.wilayas) == 2
    assert wilaya1 in zone.wilayas
    assert wilaya2 in zone.wilayas


def test_user_geography_relationships(db):
    """Test User geography relationships"""
    from app.models import User

    region = Region(name="Region")
    db.session.add(region)
    db.session.flush()

    zone = Zone(name="Zone", region_id=region.id)
    db.session.add(zone)
    db.session.flush()

    wilaya = Wilaya(name="Wilaya", zone_id=zone.id)
    db.session.add(wilaya)
    db.session.flush()

    user = User(
        username=f"user_{uuid.uuid4().hex[:10]}", # FIX: Ensure unique username
        password_hash="hash",
        role="superviseur",
        region_id=region.id,
        zone_id=zone.id,
        wilaya_id=wilaya.id,
    )
    db.session.add(user)
    db.session.commit()

    assert user.region == region
    assert user.zone == zone
    assert user.wilaya == wilaya
    assert user in region.users
    assert user in zone.users
    assert user in wilaya.users
