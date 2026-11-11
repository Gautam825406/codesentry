from app.orders import get_order


def test_get_order_returns_row():
    row = get_order("42")
    assert row is not None
