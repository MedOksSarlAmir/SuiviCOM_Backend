import pytest
import json
from sqlalchemy import text


def test_sql_injection_login(client):
    """Test SQL injection in login endpoint"""
    # Common SQL injection attempts
    injection_attempts = [
        "' OR '1'='1",
        "' OR 1=1 --",
        "admin' --",
        "' UNION SELECT * FROM users --",
        "'; DROP TABLE users; --",
    ]

    for attempt in injection_attempts:
        response = client.post(
            "/api/v1/auth/login", json={"username": attempt, "password": attempt}
        )
        # Should not crash - either 401 or 400
        assert response.status_code in [400, 401]


def test_sql_injection_search_parameters(client, auth_headers):
    """Test SQL injection in search parameters"""
    injection_attempts = [
        "' OR 1=1 --",
        "'; SELECT * FROM users; --",
        "%' OR '1'='1",
    ]

    endpoints_with_search = [
        "/api/v1/sales?search=",
        "/api/v1/purchases?search=",
        "/api/v1/vendors?search=",
        "/api/v1/visits?search=",
        "/api/v1/inventory/1?search=",
    ]

    for endpoint in endpoints_with_search:
        for attempt in injection_attempts:
            response = client.get(
                f"{endpoint}{attempt}",
                headers={"Authorization": auth_headers["Authorization"]},
            )
            # Should not crash - should return 200 or 400
            assert response.status_code in [200, 400]

            # Check no sensitive data is exposed
            if response.status_code == 200:
                data = response.json
                # Should not contain SQL error messages
                assert not any(
                    sql_keyword in str(data).upper()
                    for sql_keyword in ["SQL", "SYNTAX", "ERROR", "EXCEPTION"]
                )


def test_parameterized_queries_used(client, auth_headers, db, test_distributor):
    """Verify that parameterized queries are being used"""
    from app.controllers import sales as sales_controller

    # Mock the database to check if execute is called with parameters
    original_execute = db.session.execute

    captured_queries = []

    def capture_execute(query, params=None, **kwargs):
        captured_queries.append({"query": str(query), "params": params})
        return original_execute(query, params, **kwargs)

    # Temporarily replace execute method
    db.session.execute = capture_execute

    try:
        # Make a request that should trigger database queries
        client.get(
            f"/api/v1/sales?distributeur_id={test_distributor.id}",
            headers={"Authorization": auth_headers["Authorization"]},
        )

        # Check that at least one query was captured
        assert len(captured_queries) > 0

        # Verify queries use parameters, not string concatenation
        for query_info in captured_queries:
            query_str = query_info["query"]
            params = query_info["params"]

            # Should not have raw values in query string
            assert str(test_distributor.id) not in query_str

            # Should have parameter placeholders
            if params:
                assert ":" in query_str or "%s" in query_str or "?" in query_str

    finally:
        # Restore original method
        db.session.execute = original_execute


def test_xss_injection_attempts(client, auth_headers):
    """Test XSS injection attempts in input fields"""
    xss_attempts = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "'\"><script>alert(1)</script>",
    ]

    # Test in vendor creation
    for attempt in xss_attempts:
        response = client.post(
            "/api/v1/vendors",
            json={
                "code": f"TEST_{attempt[:10]}",
                "nom": attempt,
                "prenom": attempt,
                "vendor_type": "detail",
                "distributor_id": 1,  # Will fail but we're testing injection
            },
            headers={"Authorization": auth_headers["Authorization"]},
        )

        # Should not crash - might be 400 or 403
        assert response.status_code in [201, 400, 403, 404]

        # Check response doesn't contain the script tags
        if response.status_code != 201:
            response_text = json.dumps(response.json)
            assert "<script>" not in response_text.lower()


def test_path_traversal_attempts(client, auth_headers):
    """Test path traversal attempts"""
    traversal_attempts = [
        "../../../etc/passwd",
        "..\\..\\windows\\system32",
        "%2e%2e%2f%2e%2e%2f",
    ]

    # These are less relevant for API but good to test
    for attempt in traversal_attempts:
        response = client.get(
            f"/api/v1/sales?search={attempt}",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        # Should not crash
        assert response.status_code in [200, 400]
