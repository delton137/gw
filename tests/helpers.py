"""Shared test constants and helpers for route tests."""

TEST_USER_ID = "user_test123"


def make_auth_override(user_id: str = TEST_USER_ID):
    """Return an auth dependency override that returns a fixed user ID."""
    def _override():
        return user_id
    return _override
