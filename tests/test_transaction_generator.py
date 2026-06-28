from producer.transaction_generator import TransactionGenerator


def test_generate_transaction_has_expected_shape():
    transaction = TransactionGenerator().generate_transaction()
    data = transaction.to_dict()

    assert data["transaction_id"]
    assert data["account_id"].startswith("CH")
    assert data["account_type"] in {"CHECKING", "SAVINGS", "CREDIT", "INVESTMENT"}
    assert data["currency"] in {"CHF", "EUR", "USD", "GBP"}
    assert data["transaction_type"] in {
        "PAYMENT",
        "TRANSFER",
        "WITHDRAWAL",
        "DEPOSIT",
        "FEE",
    }
    assert data["status"] in {"COMPLETED", "PENDING", "DECLINED", "FAILED"}
    assert isinstance(data["timestamp_ms"], int)
    assert 0 <= data["risk_score"] <= 100
