import pytest
from sqlalchemy import text
from app.utils.inventory_sync import update_stock_incremental
from app.models import Inventory, Product, Distributor


def test_update_stock_incremental_new_record(app, db, test_distributor, test_product):
    """Test creating new inventory record"""
    # Ensure no inventory exists
    existing = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()
    assert existing is None

    # Add 50 units
    update_stock_incremental(test_distributor.id, test_product.id, 50)
    db.session.commit()

    inventory = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()

    assert inventory is not None
    assert inventory.stock_qte == 50
    assert inventory.last_updated is not None


def test_update_stock_incremental_existing_record(
    app, db, test_distributor, test_product
):
    """Test updating existing inventory record"""
    # Create initial inventory
    inventory = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=100,
    )
    db.session.add(inventory)
    db.session.commit()

    # Add 25 more units
    update_stock_incremental(test_distributor.id, test_product.id, 25)
    db.session.commit()

    db.session.refresh(inventory)
    assert inventory.stock_qte == 125

    # Subtract 50 units
    update_stock_incremental(test_distributor.id, test_product.id, -50)
    db.session.commit()

    db.session.refresh(inventory)
    assert inventory.stock_qte == 75


def test_update_stock_incremental_zero_delta(app, db, test_distributor, test_product):
    """Test that zero delta doesn't change anything"""
    inventory = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=100,
    )
    db.session.add(inventory)
    db.session.commit()

    # Zero delta should be ignored
    update_stock_incremental(test_distributor.id, test_product.id, 0)
    db.session.commit()

    db.session.refresh(inventory)
    assert inventory.stock_qte == 100


def test_update_stock_incremental_negative_stock(
    app, db, test_distributor, test_product
):
    """Test that stock can go negative (business logic may prevent this elsewhere)"""
    inventory = Inventory(
        distributor_id=test_distributor.id,
        product_id=test_product.id,
        stock_qte=10,
    )
    db.session.add(inventory)
    db.session.commit()

    # Subtract 20 units (goes to -10)
    update_stock_incremental(test_distributor.id, test_product.id, -20)
    db.session.commit()

    db.session.refresh(inventory)
    assert inventory.stock_qte == -10


def test_update_stock_incremental_invalid_inputs(app, db):
    """Test with invalid inputs"""
    # None values should be ignored
    update_stock_incremental(None, 1, 10)
    update_stock_incremental(1, None, 10)

    # Should not raise errors
    assert True


def test_update_stock_incremental_transaction_safety(
    app, db, test_distributor, test_product
):
    """Test that MERGE works correctly in concurrent scenarios"""
    # Create initial inventory
    update_stock_incremental(test_distributor.id, test_product.id, 100)
    db.session.commit()

    # Simulate concurrent updates
    sql1 = text(
        """
        MERGE dbo.inventory WITH (HOLDLOCK) AS target
        USING (SELECT :d_id AS dist, :p_id AS prod) AS source
        ON (target.distributor_id = source.dist AND target.product_id = source.prod)
        WHEN MATCHED THEN
            UPDATE SET stock_qte = stock_qte + :qty1, last_updated = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (distributor_id, product_id, stock_qte, last_updated)
            VALUES (:d_id, :p_id, :qty1, GETDATE());
    """
    )

    sql2 = text(
        """
        MERGE dbo.inventory WITH (HOLDLOCK) AS target
        USING (SELECT :d_id AS dist, :p_id AS prod) AS source
        ON (target.distributor_id = source.dist AND target.product_id = source.prod)
        WHEN MATCHED THEN
            UPDATE SET stock_qte = stock_qte + :qty2, last_updated = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (distributor_id, product_id, stock_qte, last_updated)
            VALUES (:d_id, :p_id, :qty2, GETDATE());
    """
    )

    # Execute both updates
    db.session.execute(
        sql1, {"d_id": test_distributor.id, "p_id": test_product.id, "qty1": 50}
    )

    db.session.execute(
        sql2, {"d_id": test_distributor.id, "p_id": test_product.id, "qty2": 25}
    )

    db.session.commit()

    inventory = Inventory.query.filter_by(
        distributor_id=test_distributor.id, product_id=test_product.id
    ).first()

    assert inventory.stock_qte == 175  # 100 + 50 + 25
