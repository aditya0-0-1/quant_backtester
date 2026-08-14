import pytest
from app import validate_payload


class TestValidatePayload:
    """Pure unit tests for validate_payload() — no Flask, no DB, no threads.
    Just: given this dict, what does the function return?
    """

    # ---------- valid input ----------

    def test_valid_payload_returns_true_and_parsed_data(self):
        payload = {"ticker": "aapl", "fast_window": 10, "slow_window": 50}
        is_valid, result = validate_payload(payload)

        assert is_valid is True
        assert result == {"ticker": "AAPL", "fast": 10, "slow": 50}

    def test_valid_payload_uses_defaults_when_windows_omitted(self):
        payload = {"ticker": "TSLA"}
        is_valid, result = validate_payload(payload)

        assert is_valid is True
        assert result["fast"] == 10
        assert result["slow"] == 50

    # ---------- missing ticker ----------


    def test_missing_ticker_is_rejected(self):
        payload = {"fast_window": 10, "slow_window": 50}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Missing 'ticker' in payload."

    def test_none_payload_is_rejected(self):
        is_valid, message = validate_payload(None)

        assert is_valid is False
        assert message == "Missing 'ticker' in payload."

    # ---------- invalid ticker ----------

    def test_ticker_not_in_database_is_rejected(self):
        payload = {"ticker": "GOOGL"}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Ticker GOOGL not found in database."

    # ---------- fast >= slow ----------

    def test_fast_window_equal_to_slow_window_is_rejected(self):
        payload = {"ticker": "AAPL", "fast_window": 50, "slow_window": 50}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Fast window must be strictly less than slow window."

    def test_fast_window_greater_than_slow_window_is_rejected(self):
        payload = {"ticker": "AAPL", "fast_window": 60, "slow_window": 50}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Fast window must be strictly less than slow window."

    # ---------- non-integer / non-positive windows ----------

    @pytest.mark.parametrize("fast,slow", [
        (10.5, 50),
        (10, 50.5),
        ("10", 50),
        (10, "50"),
    ])
    def test_non_integer_windows_are_rejected(self, fast, slow):
        payload = {"ticker": "AAPL", "fast_window": fast, "slow_window": slow}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Windows must be positive integers."

    @pytest.mark.parametrize("fast,slow", [
        (0, 50),
        (-5, 50),
        (10, 0),
        (10, -50),
    ])
    def test_non_positive_windows_are_rejected(self, fast, slow):
        payload = {"ticker": "AAPL", "fast_window": fast, "slow_window": slow}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Windows must be positive integers."

    # ---------- a real gotcha worth knowing about ----------

    def test_boolean_window_is_rejected(self):
        """
        In Python, bool is a subclass of int — isinstance(True, int) is True,
        and True == 1. validate_payload now uses `type(x) is int` instead of
        isinstance(), specifically so a boolean does NOT sneak through as a
        valid window value. This test locks that fix in place: if someone
        later "simplifies" the check back to isinstance(), this test fails
        and catches the regression.
        """
        payload = {"ticker": "AAPL", "fast_window": True, "slow_window": 50}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Windows must be positive integers."