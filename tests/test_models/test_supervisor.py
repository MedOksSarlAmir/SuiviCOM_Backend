import pytest
import uuid
from decimal import Decimal
from datetime import date
from app.models import (
    Distributor,
    Vendor,
    Product,
    ProductCategory,
    ProductType,
    Inventory,
    StockAdjustment,
    Sale,
    SaleItem,
    Purchase,
    PurchaseItem,
    Visit,
)


def test_distributor_creation(db, test_hierarchy, auth_headers):
    """Test Distributor model creation"""
    distributor = Distributor(
        nom="Test Distributor",
        wilaya_id=test_hierarchy["wilaya"].id,
        supervisor_id=auth_headers["user_id"],
        address="123 Test St",
        phone="1234567890",
        email="test@example.com",
        active=True,
    )
    db.session.add(distributor)
    db.session.commit()

    assert distributor.id is not None
    assert distributor.supervisor_id == auth_headers["user_id"]
    assert distributor.wilaya_id == test_hierarchy["wilaya"].id
    assert distributor.active is True


def test_vendor_creation(db, test_distributor, auth_headers):
    """Test Vendor model creation"""
    vendor = Vendor(
        nom="Test",
        prenom="Vendor",
        code=f"VEND_{uuid.uuid4().hex[:4]}",
        vendor_type="gros",
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
        active=True,
    )
    db.session.add(vendor)
    db.session.commit()

    assert vendor.id is not None
    assert vendor.distributor == test_distributor
    assert vendor.supervisor_id == auth_headers["user_id"]
    assert vendor.vendor_type == "gros"


def test_product_creation(db):
    """Test Product model creation"""
    category = ProductCategory(name="Beverages")
    db.session.add(category)
    db.session.flush()

    p_type = ProductType(name="Soda")
    db.session.add(p_type)
    db.session.flush()

    product = Product(
        code=f"PROD_{uuid.uuid4().hex[:6]}",
        name="Cola 1L",
        format="1L",
        category_id=category.id,
        type_id=p_type.id,
        price_factory=Decimal("50.0"),
        price_gros=Decimal("60.0"),
        price_detail=Decimal("70.0"),
        price_superette=Decimal("65.0"),
        active=True,
    )
    db.session.add(product)
    db.session.commit()

    assert product.id is not None
    assert product.category == category
    assert product.type == p_type
    assert product.price_factory == Decimal("50.0")


def test_inventory_creation(db, test_distributor, test_product):
    """Test Inventory model creation"""
    inventory = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=100,
        last_updated=date.today(),
    )
    db.session.add(inventory)
    db.session.commit()

    assert inventory.distributor_id == test_distributor.id
    assert inventory.product_id == test_product.id
    assert inventory.stock_qte == 100
    assert inventory.product == test_product
    assert inventory.distributor == test_distributor


def test_stock_adjustment_creation(db, test_distributor, test_product, auth_headers):
    """Test StockAdjustment model creation"""
    adjustment = StockAdjustment(
        date=date.today(),
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        supervisor_id=auth_headers["user_id"],
        quantity=50,
        note="Initial stock",
    )
    db.session.add(adjustment)
    db.session.commit()

    assert adjustment.id is not None
    assert adjustment.distributor == test_distributor
    assert adjustment.product == test_product
    assert adjustment.supervisor_id == auth_headers["user_id"]
    assert adjustment.quantity == 50


def test_sale_creation(db, test_distributor, test_vendor, auth_headers):
    """Test Sale model creation"""
    sale = Sale(
        date=date.today(),
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
        montant_total=Decimal("1000.00"),
    )
    db.session.add(sale)
    db.session.commit()

    assert sale.id is not None
    assert sale.distributor == test_distributor
    assert sale.vendor == test_vendor
    assert sale.supervisor_id == auth_headers["user_id"]
    assert sale.status == "complete"


def test_sale_item_creation(
    db, test_distributor, test_vendor, test_product, auth_headers
):
    """Test SaleItem model creation"""
    sale = Sale(
        date=date.today(),
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        supervisor_id=auth_headers["user_id"],
    )
    db.session.add(sale)
    db.session.flush()

    sale_item = SaleItem(
        sale_id=sale.id,
        product_id=test_product.id,
        quantity=10,
    )
    db.session.add(sale_item)
    db.session.commit()

    assert sale_item.id is not None
    assert sale_item.sale == sale
    assert sale_item.product == test_product
    assert sale_item.quantity == 10


def test_purchase_creation(db, test_distributor, auth_headers):
    """Test Purchase model creation"""
    purchase = Purchase(
        date=date.today(),
        distributor_id=test_distributor.id,
        supervisor_id=auth_headers["user_id"],
        montant_total=Decimal("5000.00"),
        status="en_cours",
    )
    db.session.add(purchase)
    db.session.commit()

    assert purchase.id is not None
    assert purchase.distributor == test_distributor
    assert purchase.supervisor_id == auth_headers["user_id"]
    assert purchase.status == "en_cours"


def test_visit_creation(db, test_distributor, test_vendor, auth_headers):
    """Test Visit model creation"""
    visit = Visit(
        date=date.today(),
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        supervisor_id=auth_headers["user_id"],
        visites_programmees=5,
        visites_effectuees=3,
        nb_factures=2,
        status="effectuée",
    )
    db.session.add(visit)
    db.session.commit()

    assert visit.id is not None
    assert visit.distributor == test_distributor
    assert visit.vendor == test_vendor
    assert visit.supervisor_id == auth_headers["user_id"]
    assert visit.status == "effectuée"


def test_view_models(db):
    """Test that view models can be queried"""
    from app.models import (
        SaleView,
        PurchaseView,
        ProductView,
        DistributorView,
        InventoryHistoryView,
        VisitView,
    )

    # Test that views exist and can be queried without error
    sale_views = SaleView.query.limit(1).all()
    purchase_views = PurchaseView.query.limit(1).all()
    product_views = ProductView.query.limit(1).all()
    distributor_views = DistributorView.query.limit(1).all()
    inventory_views = InventoryHistoryView.query.limit(1).all()
    visit_views = VisitView.query.limit(1).all()

    # Just ensure no errors
    assert isinstance(sale_views, list)
    assert isinstance(purchase_views, list)
    assert isinstance(product_views, list)
    assert isinstance(distributor_views, list)
    assert isinstance(inventory_views, list)
    assert isinstance(visit_views, list)
