import pytest
import uuid
import time
import threading
from unittest.mock import patch
from flask import g

def test_double_click_sale_creation(client, auth_headers, db, test_distributor, test_vendor, test_product):
    """Test duplicate sale creation from double-click"""
    from app.models import Sale, Inventory
    from app.extensions import db as _db
    
    # Setup inventory
    inv = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=100
    )
    _db.session.add(inv)
    _db.session.commit()
    
    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [{"product_id": test_product.id, "quantity": 10}],
        # Add idempotency key
        "idempotency_key": f"sale_{uuid.uuid4()}"
    }
    
    # First request - should succeed
    response1 = client.post(
        "/api/v1/sales",
        json=sale_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response1.status_code == 201
    first_sale_id = response1.json.get("id")
    
    # Immediately send identical request (double-click scenario)
    response2 = client.post(
        "/api/v1/sales",
        json=sale_data,  # Same idempotency key
        headers={"Authorization": auth_headers["Authorization"]},
    )
    
    # Should either:
    # 1. Return 409 Conflict (with existing sale)
    # 2. Return 200 with same sale ID (idempotent)
    # 3. Return 400 Bad Request
    assert response2.status_code in [200, 201, 409, 400]
    
    if response2.status_code in [200, 201]:
        # If success, must be same sale
        second_sale_id = response2.json.get("id")
        assert second_sale_id == first_sale_id, "Duplicate sale created!"
    
    # Count sales with this distributor/vendor/date combo
    sales_count = Sale.query.filter_by(
        distributor_id=test_distributor.id,
        vendor_id=test_vendor.id,
        date="2026-02-03"
    ).count()
    
    assert sales_count == 1, f"Expected 1 sale, found {sales_count} (duplicate created)"
    
    # Verify inventory only deducted once
    _db.session.refresh(inv)
    assert inv.stock_qte == 90, f"Expected stock 90, got {inv.stock_qte} (duplicate deduction)"


def test_concurrent_identical_requests(app, auth_headers, test_distributor, test_vendor, test_product):
    """Test multiple threads sending identical requests simultaneously"""
    sale_data = {
        "acteurId": test_vendor.id,
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [{"product_id": test_product.id, "quantity": 5}],
        "idempotency_key": f"concurrent_{uuid.uuid4()}"
    }
    
    results = []
    
    def make_request(request_id):
        with app.test_client() as thread_client:
            response = thread_client.post(
                "/api/v1/sales",
                json=sale_data,
                headers={"Authorization": auth_headers["Authorization"]},
            )
            results.append({
                'request_id': request_id,
                'status': response.status_code,
                'sale_id': response.json.get('id') if response.status_code in [200, 201] else None
            })
    
    # Launch 5 identical requests simultaneously
    threads = []
    for i in range(5):
        t = threading.Thread(target=make_request, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Analyze results
    successful_requests = [r for r in results if r['status'] in [200, 201]]
    sale_ids = set(r['sale_id'] for r in successful_requests if r['sale_id'])
    
    # Should create only 1 sale, or all return same sale ID
    assert len(sale_ids) <= 1, f"Multiple sales created from identical requests: {sale_ids}"
    
    if successful_requests:
        # All successful requests should reference same sale
        first_sale_id = successful_requests[0]['sale_id']
        for req in successful_requests:
            assert req['sale_id'] == first_sale_id, "Inconsistent sale IDs"


def test_purchase_double_submit_inventory_safety(client, auth_headers, db, test_distributor, test_product):
    """Test purchase double-submit doesn't double-add inventory"""
    from app.models import Purchase, Inventory
    
    # Initial inventory
    inv = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=50
    )
    db.session.add(inv)
    db.session.commit()
    
    purchase_data = {
        "distributeurId": test_distributor.id,
        "date": "2026-02-03",
        "status": "complete",
        "products": [{"product_id": test_product.id, "quantity": 30}],
        "request_id": f"purchase_{uuid.uuid4()}"  # Unique request ID
    }
    
    # Simulate double-click with small delay
    response1 = client.post(
        "/api/v1/purchases",
        json=purchase_data,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response1.status_code == 201
    
    # Second request (could be browser refresh or duplicate API call)
    response2 = client.post(
        "/api/v1/purchases",
        json=purchase_data,  # Same data
        headers={"Authorization": auth_headers["Authorization"]},
    )
    
    # Check inventory
    db.session.refresh(inv)
    # Should be 50 + 30 = 80, NOT 50 + 30 + 30 = 110
    assert inv.stock_qte == 80, f"Double inventory addition! Stock: {inv.stock_qte}"
    
    # Count purchases
    purchase_count = Purchase.query.filter_by(
        distributor_id=test_distributor.id,
        date="2026-02-03"
    ).count()
    
    assert purchase_count == 1, f"Duplicate purchase created: {purchase_count} purchases"


# Add idempotency middleware test
def test_idempotency_middleware(client, auth_headers):
    """Test idempotency middleware if implemented"""
    # Create endpoint that simulates non-idempotent operation
    test_key = f"test_{uuid.uuid4()}"
    
    # First request
    response1 = client.post(
        "/api/v1/test/charge",  # Hypothetical charging endpoint
        json={"amount": 100, "idempotency_key": test_key},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    
    # Second identical request
    response2 = client.post(
        "/api/v1/test/charge",
        json={"amount": 100, "idempotency_key": test_key},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    
    # Should get same result
    if response1.status_code == 200 and response2.status_code == 200:
        assert response1.json.get("transaction_id") == response2.json.get("transaction_id")