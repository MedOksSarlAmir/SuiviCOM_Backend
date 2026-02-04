import pytest
import uuid
import os
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db as _db
from app.models import (
    User,
    Region,
    Zone,
    Wilaya,
    Distributor,
    Product,
    Vendor,
    ProductCategory,
    ProductType,
)
from app.extensions import bcrypt


@pytest.fixture(scope="session")
def app():
    # Force use of test database
    os.environ["DB_NAME"] = os.getenv("DB_NAME", "suivi_com") + "_test"
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_SECRET_KEY": "test-secret-key",
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(minutes=5),  # Shorter for tests
        }
    )
    with app.app_context():
        yield app


@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        # Setup modern transaction handling for Flask-SQLAlchemy 3.0+
        connection = _db.engine.connect()
        transaction = connection.begin()
        _db.session.bind = connection

        yield _db

        _db.session.remove()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client, app, db):
    """Standard supervisor auth headers"""
    unique_username = f"sup_{uuid.uuid4().hex[:6]}"
    user = User(
        username=unique_username,
        password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
        role="superviseur",
        nom="Test",
        prenom="Supervisor",
    )
    db.session.add(user)
    db.session.flush()

    from flask_jwt_extended import create_access_token

    token = create_access_token(
        identity=str(user.id), additional_claims={"role": "superviseur"}
    )
    return {
        "Authorization": f"Bearer {token}",
        "username": unique_username,
        "user_id": user.id,
        "user": user,
    }


@pytest.fixture
def admin_auth_headers(client, app, db):
    """Admin user auth headers"""
    unique_username = f"admin_{uuid.uuid4().hex[:6]}"
    user = User(
        username=unique_username,
        password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
        role="admin",
        nom="Admin",
        prenom="User",
    )
    db.session.add(user)
    db.session.flush()

    from flask_jwt_extended import create_access_token

    token = create_access_token(
        identity=str(user.id), additional_claims={"role": "admin"}
    )
    return {
        "Authorization": f"Bearer {token}",
        "user_id": user.id,
        "user": user,
    }


@pytest.fixture
def test_hierarchy(db):
    """Create a complete geography hierarchy"""
    reg = Region(name=f"Region_{uuid.uuid4().hex[:4]}")
    db.session.add(reg)
    db.session.flush()

    zn = Zone(name=f"Zone_{uuid.uuid4().hex[:4]}", region_id=reg.id)
    db.session.add(zn)
    db.session.flush()

    wil = Wilaya(name=f"Wilaya_{uuid.uuid4().hex[:4]}", zone_id=zn.id)
    db.session.add(wil)
    db.session.flush()

    return {"region": reg, "zone": zn, "wilaya": wil}


@pytest.fixture
def test_distributor(db, test_hierarchy, auth_headers):
    """Create a test distributor for the test supervisor"""
    dist = Distributor(
        nom=f"Dist_{uuid.uuid4().hex[:4]}",
        wilaya_id=test_hierarchy["wilaya"].id,
        supervisor_id=auth_headers["user_id"],
        active=True,
    )
    db.session.add(dist)
    db.session.flush()
    return dist


@pytest.fixture
def test_product(db):
    """Create a test product"""
    # First create category and type
    cat = ProductCategory(name=f"Cat_{uuid.uuid4().hex[:4]}")
    db.session.add(cat)
    db.session.flush()

    p_type = ProductType(name=f"Type_{uuid.uuid4().hex[:4]}")
    db.session.add(p_type)
    db.session.flush()

    prod = Product(
        code=f"PROD_{uuid.uuid4().hex[:6]}",
        designation="Test Product",
        format="1L",
        category_id=cat.id,
        type_id=p_type.id,
        price_factory=50.0,
        price_gros=60.0,
        price_detail=70.0,
        price_superette=65.0,
        active=True,
    )
    db.session.add(prod)
    db.session.commit()
    return prod


@pytest.fixture
def test_vendor(db, test_distributor, auth_headers):
    """Create a test vendor"""
    vend = Vendor(
        nom=f"Vendor_{uuid.uuid4().hex[:4]}",
        prenom="Test",
        code=f"VEND_{uuid.uuid4().hex[:4]}",
        vendor_type="detail",
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
        active=True,
    )
    db.session.add(vend)
    db.session.commit()
    return vend
