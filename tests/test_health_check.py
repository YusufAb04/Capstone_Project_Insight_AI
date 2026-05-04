import pytest
import requests
from unittest.mock import patch, MagicMock
from src.health_check import (
    check_embedding_model,
    check_ollama,
    check_disk,
    CheckResult,
)


def test_check_embedding_model_ok():
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.0] * 384
    with patch("src.health_check._SentenceTransformer", return_value=mock_model):
        result = check_embedding_model()
    assert result.status == "ok"


def test_check_embedding_model_wrong_dims():
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.0] * 100
    with patch("src.health_check._SentenceTransformer", return_value=mock_model):
        result = check_embedding_model()
    assert result.status == "fail"
    assert "384" in result.message


def test_check_embedding_model_import_error():
    with patch("src.health_check._SentenceTransformer", None):
        result = check_embedding_model()
    assert result.status == "fail"
    assert "pip install" in result.fix


def test_check_ollama_ok():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
    with patch("src.health_check.requests.get", return_value=mock_resp):
        result = check_ollama("http://localhost:11434", "llama3.2:3b")
    assert result.status == "ok"


def test_check_ollama_model_not_pulled():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": []}
    with patch("src.health_check.requests.get", return_value=mock_resp):
        result = check_ollama("http://localhost:11434", "llama3.2:3b")
    assert result.status == "warn"
    assert "ollama pull" in result.fix


def test_check_ollama_unreachable():
    with patch("src.health_check.requests.get", side_effect=requests.exceptions.ConnectionError()):
        result = check_ollama("http://localhost:11434", "llama3.2:3b")
    assert result.status == "fail"
    assert "ollama serve" in result.fix


def test_check_disk_writable(tmp_path):
    result = check_disk(str(tmp_path / "data"))
    assert result.status == "ok"


def test_check_disk_cloud_sync_onedrive(tmp_path):
    cloud_path = str(tmp_path) + "/OneDrive/MyProject/data"
    result = check_disk(cloud_path)
    assert result.status == "warn"
    assert "cloud" in result.fix.lower() or "onedrive" in result.fix.lower()


def test_check_disk_cloud_sync_google_drive(tmp_path):
    cloud_path = str(tmp_path) + "/Google Drive/MyProject/data"
    result = check_disk(cloud_path)
    assert result.status == "warn"
