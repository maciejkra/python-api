import json
from fastapi.testclient import TestClient
import pytest
from unittest.mock import MagicMock
import redis
import socket

# Import the app instance from the code file
from main import app, get_redis, CustomJSONResponse

client = TestClient(app)
app.hostname = socket.gethostname()

@pytest.fixture
def mock_redis(monkeypatch):
    mock_redis = MagicMock()
    monkeypatch.setattr("main.get_redis", lambda: mock_redis)
    return mock_redis


def test_info():
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == b'{"message":"Hello World","hostname":"%s"}\n' % app.hostname.encode()


def test_healthz_ok(mock_redis):
    mock_redis.ping.return_value = True

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b'{"message":"Service is OK","hostname":"%s"}\n' % app.hostname.encode()


def test_healthz_not_ok(mock_redis):
    mock_redis.ping.side_effect = redis.exceptions.ConnectionError

    response = client.get("/healthz")
    assert response.status_code == 500
    assert response.content == b'{"message":"Service is NOT OK","hostname":"%s"}\n' % app.hostname.encode()


def test_info_get(mock_redis):
    mock_redis.get.return_value = 42

    response = client.get("/api/v1/info")
    assert response.status_code == 200
    assert response.content == b'{"message":"Counter","hostname":"%s","value":42}\n' % app.hostname.encode()


def test_info_post_no_previous(mock_redis):
    mock_redis.get.return_value = None

    response = client.post("/api/v1/info")
    assert response.status_code == 200
    assert response.content == b'{"message":"OK","hostname":"%s"}\n' % app.hostname.encode()
    mock_redis.set.assert_called_once_with('counter', 1)


def test_info_post_with_previous(mock_redis):
    mock_redis.get.return_value = 42

    response = client.post("/api/v1/info")
    assert response.status_code == 200
    assert response.content == b'{"message":"OK","hostname":"%s"}\n' % app.hostname.encode()
    mock_redis.incr.assert_called_once_with('counter')


def test_custom_json_response():
    content = {"test": "value"}
    response = CustomJSONResponse(content)
    assert response.render(content) == b'{"test":"value"}\n'
