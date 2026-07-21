from datetime import UTC, datetime

from portfolio_monitor.models import TransactionInput, TransactionType


def buy(key: str, quantity: float = 100, price: float = 1.2):
    return TransactionInput(transaction_type=TransactionType.BUY, symbol="159995.SZ", quantity=quantity,
                            price=price, fees=5, traded_at=datetime.now(UTC), idempotency_key=key)


def test_idempotent_transaction_and_position_rebuild(database):
    first = database.record_transaction(buy("same"))
    duplicate = database.record_transaction(buy("same"))
    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    assert len(database.list_transactions()) == 1
    position = database.list_positions()[0]
    assert position["quantity"] == 100
    assert database.cash_balance(1_000_000) == 1_000_000 - 125


def test_correction_is_audited_and_atomic(database):
    original = database.record_transaction(buy("original"))
    replacement = buy("replacement", quantity=200, price=1.1)
    corrected = database.correct_transaction(original["id"], replacement)
    assert corrected["corrected_from_id"] == original["id"]
    assert database.list_positions()[0]["quantity"] == 200
    with database.connect() as connection:
        assert connection.execute("SELECT status FROM transactions WHERE id=?", (original["id"],)).fetchone()[0] == "corrected"
