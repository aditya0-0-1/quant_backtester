import os

# NEW: set this BEFORE `from app import app` runs.
# Why: app.py reads API_KEY via os.environ.get(...) at import time — the
# instant Python executes the `from app import app` line below, not later.
# If we don't set it here first, these tests silently depend on whatever
# API_KEY happens to be set (or not set) in whoever's shell runs pytest —
# passing on your machine, failing on a teammate's or in CI, for a reason
# that has nothing to do with your code being wrong.
os.environ["API_KEY"] = "test-secret-key"

import pytest
from app import app 


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


VALID_HEADERS = {"X-API-Key": "test-secret-key"}


# ---------- Testing the Front Door (Now with Auth) ----------

def test_run_backtest_valid_payload(client):
    response = client.post('/api/run-backtest', json={
        "ticker": "AAPL",
        "fast_window": 10,
        "slow_window": 50
    }, headers=VALID_HEADERS)

    assert response.status_code == 202
    data = response.get_json()
    assert data["status"] == "processing"


def test_run_backtest_invalid_json_body(client):
    response = client.post('/api/run-backtest', data="This is not JSON text", headers=VALID_HEADERS)
    assert response.status_code == 400


def test_run_backtest_missing_ticker_returns_400(client):
    response = client.post('/api/run-backtest', json={
        "fast_window": 10,
        "slow_window": 50
    }, headers=VALID_HEADERS)

    assert response.status_code == 400
    assert response.get_json()["message"] == "Missing 'ticker' in payload."


# ---------- Day 14 tests: auth ----------
#
# NOTE: both tests below assert the SAME message for two DIFFERENT failure
# reasons (no header at all, vs. a wrong header value). That's intentional —
# see the comment on require_api_key in app.py. If you ever "clean up" the
# auth code back into two separate branches with two separate messages,
# these two tests should be the ones that catch it.

def test_missing_api_key_is_rejected(client):
    """A perfect payload, but no API key at all."""
    response = client.post('/api/run-backtest', json={
        "ticker": "AAPL",
        "fast_window": 10,
        "slow_window": 50
    })  # no headers passed

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid or missing API key."


def test_wrong_api_key_is_rejected(client):
    """A key was sent, but it's not the right one."""
    response = client.post('/api/run-backtest', json={
        "ticker": "AAPL"
    }, headers={"X-API-Key": "i-am-a-hacker"})

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid or missing API key."


# ---------- Testing global error handlers ----------

def test_global_404_handler_catches_bad_urls(client):
    response = client.post('/api/run-bcktest-typo')
    assert response.status_code == 404


def test_global_405_handler_catches_wrong_methods(client):
    response = client.get('/api/run-backtest')
    assert response.status_code == 405