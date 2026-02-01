from app.extensions import db
from sqlalchemy import text

def update_stock_incremental(dist_id, prod_id, delta):
    """
    delta: positive to add stock, negative to subtract.
    Handles the creation of the row if it doesn't exist.
    """
    if not dist_id or not prod_id or delta == 0:
        return
    # Using a Merge/Upsert logic for MSSQL
    sql = text(
        """
        MERGE dbo.inventory AS target
        USING (SELECT :d_id AS dist, :p_id AS prod) AS source
        ON (target.distributor_id = source.dist AND target.product_id = source.prod)
        WHEN MATCHED THEN
            UPDATE SET stock_qte = stock_qte + :qty, last_updated = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (distributor_id, product_id, stock_qte, last_updated)
            VALUES (:d_id, :p_id, :qty, GETDATE());
    """
    )
    db.session.execute(sql, {"d_id": dist_id, "p_id": prod_id, "qty": delta})
