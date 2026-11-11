"""Safe pattern for contrast: parameterised query, no interpolation."""
from app.db import run_query


def get_user(user_id):
    return run_query("SELECT * FROM users WHERE id = %s", (user_id,))
