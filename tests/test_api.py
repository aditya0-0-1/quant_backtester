import os
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


def test_run_backtest_oversized_window_returns_400(client):
    """NEW: locks in the upper-bound validation fix."""
    response = client.post('/api/run-backtest', json={
        "ticker": "AAPL",
        "fast_window": 10,
        "slow_window": 999999
    }, headers=VALID_HEADERS)

    assert response.status_code == 400
    assert "must not exceed" in response.get_json()["message"]


# ---------- Day 14 tests: auth ----------

def test_missing_api_key_is_rejected(client):
    response = client.post('/api/run-backtest', json={
        "ticker": "AAPL",
        "fast_window": 10,
        "slow_window": 50
    })

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid or missing API key."


def test_wrong_api_key_is_rejected(client):
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