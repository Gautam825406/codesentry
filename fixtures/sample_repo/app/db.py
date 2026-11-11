import sqlite3


def get_connection():
    return sqlite3.connect("shop.db")


def run_query(sql, params=None):
    # Executes whatever SQL it is given. Safe when the caller parameterises,
    # unsafe when the caller interpolates. The demo PR changes the caller.
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    rows = cursor.fetchall()
    conn.close()
    return rows
