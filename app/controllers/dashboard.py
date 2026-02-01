from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db # <--- Correct
from app.models import Sale, User
from sqlalchemy import func


def get_stats():
    user_id = get_jwt_identity()
    
    total_sales_count = Sale.query.filter_by(supervisor_id=user_id).count()

    return jsonify({
        "data": {
            "totalSales": total_sales_count,
            # ... rest of your code
        }
    }), 200