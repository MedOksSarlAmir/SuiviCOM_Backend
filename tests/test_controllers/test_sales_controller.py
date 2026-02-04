import pytest
import uuid
from decimal import Decimal
from datetime import date, timedelta
from app.models import Sale, SaleItem, Vendor, Distributor, Product, Inventory


def test_get_sales_pagination(
    client, auth_headers, db, test_distributor, test_vendor, test_product
):
    """Test sales pagination"""
    # Create multiple sales
    for i in range(15):
        sale = Sale(
            date=date.today(),
            distributor_id=test_distributor.id,
            vendor_id=test_vendor.id,
            supervisor_id=auth_headers["user_id"],
            status="complete",
            montant_total=Decimal(f"{100 + i}.00"),
        )
        db.session.add(sale)
        db.session.flush()

        item = SaleItem(
            sale_id=sale.id,
            product_id=test_product.id,
            quantity=i + 1,
        )
        db.session.add(item)

    db.session.commit()

    # Test page 1
    response = client.get(
        "/api/v1/sales?page=1&pageSize=10",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200
    assert len(response.json["data"]) == 10
    assert response.json["total"] == 15

    # Test page 2
    response = client.get(
        "/api/v1/sales?page=2&pageSize=10",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200
    assert len(response.json["data"]) == 5


def test_get_sales_with_filters(
    client, auth_headers, db, test_distributor, test_vendor
):
    """Test sales with various filters"""
    # Create sales with different dates and statuses
    today = date.today()
    yesterday = today - timedelta(days=1)

    sale1 = Sale(
        date=yesterday,
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",
        montant_total=Decimal("1000.00"),
    )

    sale2 = Sale(
        date=today,
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="en_cours",
        montant_total=Decimal("500.00"),
    )

    db.session.add_all([sale1, sale2])
    db.session.commit()

    # Filter by date range
    response = client.get(
        f"/api/v1/sales?startDate={yesterday}&endDate={yesterday}",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200
    assert len(response.json["data"]) == 1
    assert response.json["data"][0]["date"] == yesterday.isoformat()

    # Filter by status
    response = client.get(
        "/api/v1/sales?status=complete",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200
    assert len(response.json["data"]) == 1
    assert response.json["data"][0]["status"] == "complete"

    # Filter by distributor
    response = client.get(
        f"/api/v1/sales?distributeur_id={test_distributor.id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200
    assert len(response.json["data"]) == 2


def test_create_sale_with_multiple_products(
    client, auth_headers, db, test_distributor, test_vendor, test_product
):
    """Test creating sale with multiple products"""
    # Create another product
    from app.models import Product

    product2 = Product(
        code=f"PROD2_{uuid.uuid4().hex[:6]}",
        designation="Test Product 2",
        price_detail=Decimal("150.0"),
        active=True,
    )
    db.session.add(product2)
    db.session.commit()

    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": date.today().isoformat(),
        "status": "complete",
        "products": [
            {"product_id": test_product.id, "quantity": 5},
            {"product_id": product2.id, "quantity": 3},
        ],
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 201
    assert "id" in response.json

    # Verify stock was reduced
    inventory1 = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()

    if inventory1:
        assert inventory1.stock_qte == -5  # Was 0, sold 5 = -5

    inventory2 = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=product2.id
    ).first()

    if inventory2:
        assert inventory2.stock_qte == -3


def test_create_sale_zero_quantity(
    client, auth_headers, test_distributor, test_vendor, test_product
):
    """Test creating sale with zero quantity (should be ignored)"""
    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": date.today().isoformat(),
        "status": "complete",
        "products": [
            {"product_id": test_product.id, "quantity": 0},  # Zero quantity
            {"product_id": test_product.id, "quantity": -5},  # Negative quantity
        ],
    }

    response = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Should succeed but ignore zero/negative quantities
    assert response.status_code == 201

    # Verify no sale items were created
    sale_id = response.json["id"]
    sale = Sale.query.get(sale_id)
    assert len(sale.items) == 0


def test_update_sale(
    client, auth_headers, db, test_distributor, test_vendor, test_product
):
    """Test updating a sale"""
    # Create initial sale
    sale = Sale(
        date=date.today(),
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="en_cours",
        montant_total=Decimal("0.00"),
    )
    db.session.add(sale)
    db.session.flush()

    item = SaleItem(
        sale_id=sale.id,
        product_id=test_product.id,
        quantity=10,
    )
    db.session.add(item)
    db.session.commit()

    # Update sale
    update_data = {
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "status": "complete",
        "distributorId": test_distributor.id,
        "vendorId": test_vendor.id,
        "products": [{"product_id": test_product.id, "quantity": 20}],
    }

    response = client.put(
        f"/api/v1/sales/{sale.id}",
        json=update_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200
    assert response.json["message"] == "Mise à jour réussie"

    # Verify update
    db.session.refresh(sale)
    assert sale.date == date.today() + timedelta(days=1)
    assert sale.status == "complete"
    assert len(sale.items) == 1
    assert sale.items[0].quantity == 20


def test_delete_sale(
    client, auth_headers, db, test_distributor, test_vendor, test_product
):
    """Test deleting a sale"""
    # Create sale with inventory impact
    sale = Sale(
        date=date.today(),
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        supervisor_id=auth_headers["user_id"],
        status="complete",  # Will affect inventory
        montant_total=Decimal("1000.00"),
    )
    db.session.add(sale)
    db.session.flush()

    item = SaleItem(
        sale_id=sale.id,
        product_id=test_product.id,
        quantity=10,
    )
    db.session.add(item)
    db.session.commit()

    # Record initial inventory
    inventory = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()
    initial_stock = inventory.stock_qte if inventory else 0

    # Delete sale
    response = client.delete(
        f"/api/v1/sales/{sale.id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    assert response.status_code == 200
    assert response.json["message"] == "Supprimé"

    # Verify sale is deleted
    assert Sale.query.get(sale.id) is None

    # Verify inventory was restored
    if inventory:
        db.session.refresh(inventory)
        assert inventory.stock_qte == initial_stock + 10  # Added back 10 units


def test_weekly_matrix_endpoint(
    client, auth_headers, test_distributor, test_vendor, test_product
):
    """Test weekly sales matrix endpoint"""
    # Test with missing parameters
    response = client.get(
        "/api/v1/sales/weekly-matrix",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 400

    # Test with all parameters
    response = client.get(
        f"/api/v1/sales/weekly-matrix?start_date={date.today().isoformat()}&vendor_id={test_vendor.id}&distributor_id={test_distributor.id}",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200
    assert "data" in response.json
    assert "dates" in response.json
    assert "statuses" in response.json
