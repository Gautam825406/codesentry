from app.db import run_query


def get_order(order_id):
    sql = f"SELECT * FROM orders WHERE id = '{order_id}'"
    return run_query(sql)


def average_price(prices):
    total = sum(prices)
    return total / len(prices)
