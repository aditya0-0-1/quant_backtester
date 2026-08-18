import pytest
from app import validate_payload


class TestValidatePayload:
    """Pure unit tests for validate_payload() — no Flask, no DB, no threads."""

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
        # CHANGED: message updated to reflect reality — this is a fixed
        # in-memory dict lookup, not a database query.
        assert message == "Ticker GOOGL not supported."

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

    # ---------- NEW: upper bound on window size ----------

    @pytest.mark.parametrize("fast,slow", [
        (501, 600),
        (10, 501),
        (600, 900),
    ])
    def test_oversized_windows_are_rejected(self, fast, slow):
        payload = {"ticker": "AAPL", "fast_window": fast, "slow_window": slow}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Windows must not exceed 500."

    def test_window_exactly_at_max_is_accepted(self):
        payload = {"ticker": "AAPL", "fast_window": 400, "slow_window": 500}
        is_valid, result = validate_payload(payload)

        assert is_valid is True
        assert result["slow"] == 500

    # ---------- boolean gotcha ----------

    def test_boolean_window_is_rejected(self):
        """
        bool is a subclass of int in Python — isinstance(True, int) is True.
        validate_payload uses `type(x) is int` specifically so a boolean
        doesn't sneak through as a valid window value.
        """
        payload = {"ticker": "AAPL", "fast_window": True, "slow_window": 50}
        is_valid, message = validate_payload(payload)

        assert is_valid is False
        assert message == "Windows must be positive integers."