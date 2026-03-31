import pytest
from unittest.mock import patch
import httpx

def test_health_ok(client):
    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock a successful response from sd-server
        mock_response = httpx.Response(200, json={})
        mock_get.return_value = mock_response

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["api"] == "ok"
        assert data["sd_server"] == "ok"

def test_health_degraded(client):
    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock a connection error from sd-server
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["sd_server"] == "unreachable"

def test_list_models_success(client):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = httpx.Response(200, json=[{"model_name": "test_model"}], request=httpx.Request("GET", "http://test"))
        mock_get.return_value = mock_response

        response = client.get("/models")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["model_name"] == "test_model"

def test_list_models_unreachable(client):
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection failed")):
        response = client.get("/models")
        assert response.status_code == 502

def test_list_samplers(client):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = httpx.Response(200, json=[{"name": "Euler a"}], request=httpx.Request("GET", "http://test"))
        mock_get.return_value = mock_response

        response = client.get("/samplers")
        assert response.status_code == 200
        assert response.json()[0]["name"] == "Euler a"
