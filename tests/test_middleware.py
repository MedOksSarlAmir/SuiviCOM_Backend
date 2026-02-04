from sqlalchemy import text


def test_db_session_context_is_set(client, auth_headers, db):
    """
    Test that session context is set.
    NOTE: We must use a non-auth route because auth routes are skipped in middleware.
    """
    # Call distributors instead of /me
    client.get(
        "/api/v1/supervisor/distributors",
        headers={"Authorization": auth_headers["Authorization"]},
    )

    # Query SQL Server context
    result = db.session.execute(text("SELECT SESSION_CONTEXT(N'user_id')")).scalar()

    assert result is not None
    assert int(result) == auth_headers["user_id"]
