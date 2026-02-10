# New file: /tests/test_security/test_concurrency.py
import pytest
import threading
import time
from sqlalchemy import create_engine, text
from app.utils.inventory_sync import update_stock_incremental


def test_real_concurrent_stock_updates(app):
    """Test REAL parallel updates to detect lost updates"""
    # Create two separate database connections (simulating concurrent users)
    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])

    # Setup test data in main thread
    with app.app_context():
        from app.models import Distributor, Product, Inventory
        from app.extensions import db

        # Create test distributor and product
        dist = Distributor(nom="Concurrent_Test", wilaya_id=1, supervisor_id=1)
        prod = Product(code="CONC_PROD", name="Concurrent Product")
        db.session.add_all([dist, prod])
        db.session.commit()

        # Initialize inventory
        inv = Inventory(distributor_id=dist.id, product_id=prod.id, stock_qte=100)
        db.session.add(inv)
        db.session.commit()

        dist_id = dist.id
        prod_id = prod.id

    results = []
    lock = threading.Lock()

    def concurrent_update(thread_id, delta, delay=0):
        """Worker thread that performs stock update"""
        time.sleep(delay)  # Stagger threads

        # Each thread gets its OWN database connection
        thread_engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
        with thread_engine.connect() as conn:
            with conn.begin():
                # Use the actual update function
                sql = text(
                    """
                    MERGE dbo.inventory WITH (HOLDLOCK) AS target
                    USING (SELECT :d_id AS dist, :p_id AS prod) AS source
                    ON (target.distributor_id = source.dist AND target.product_id = source.prod)
                    WHEN MATCHED THEN
                        UPDATE SET stock_qte = stock_qte + :delta
                    WHEN NOT MATCHED THEN
                        INSERT (distributor_id, product_id, stock_qte)
                        VALUES (:d_id, :p_id, :delta);
                """
                )
                conn.execute(sql, {"d_id": dist_id, "p_id": prod_id, "delta": delta})

        with lock:
            results.append((thread_id, delta))

    # Launch 10 concurrent updates (5 add 10, 5 subtract 5)
    threads = []
    for i in range(5):
        t = threading.Thread(target=concurrent_update, args=(i, 10, i * 0.01))
        threads.append(t)

    for i in range(5, 10):
        t = threading.Thread(target=concurrent_update, args=(i, -5, i * 0.01))
        threads.append(t)

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    # Verify final stock
    with app.app_context():
        from app.extensions import db
        from app.models import Inventory

        final_inv = Inventory.query.filter_by(
            distributor_id=dist_id, product_id=prod_id
        ).first()

        # Should be: 100 + (5*10) + (5*-5) = 100 + 50 - 25 = 125
        # If lost updates occur, result will be different
        assert (
            final_inv.stock_qte == 125
        ), f"Lost update detected! Got {final_inv.stock_qte}, expected 125"


def test_concurrent_sale_creation_race_condition(
    client, auth_headers, app, db, test_distributor, test_vendor, test_product
):
    """Test race condition when multiple sales are created simultaneously"""
    # Initialize inventory
    from app.models import Inventory

    inv = Inventory(
        distributor_id=test_distributor.id, product_id=test_product.id, stock_qte=100
    )
    db.session.add(inv)
    db.session.commit()

    results = []
    errors = []

    def create_sale(sale_id):
        """Worker to create sale"""
        with app.app_context(): 
            try:
                with app.test_client() as thread_client:
                    sale_data = {
                        "acteurId": test_vendor.id,
                        "distributeurId": test_distributor.id,
                        "date": "2026-02-03",
                        "status": "complete",
                        "products": [{"product_id": test_product.id, "quantity": 5}],
                    }

                    response = thread_client.post(
                        "/api/v1/sales",
                        json=sale_data,
                        headers={"Authorization": auth_headers["Authorization"]},
                    )
                    results.append((sale_id, response.status_code))
            except Exception as e:
                errors.append((sale_id, str(e)))

    # Launch 5 concurrent sales
    threads = []
    for i in range(5):
        t = threading.Thread(target=create_sale, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Check results
    assert len(errors) == 0, f"Errors occurred: {errors}"

    # Verify inventory
    db.session.refresh(inv)
    # Should be: 100 - (5 sales * 5 quantity) = 75
    # If race condition: might be wrong (e.g., 100 - 5 = 95 if updates lost)
    assert (
        inv.stock_qte == 75
    ), f"Race condition detected! Stock: {inv.stock_qte}, expected 75"
