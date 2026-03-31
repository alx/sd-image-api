import pytest
from unittest.mock import patch
import base64
from main import OUTPUT_DIR

DUMMY_IMAGE_B64 = base64.b64encode(b'dummy_image_data_png_here').decode('utf-8')

@patch("main.call_txt2img")
def test_generate_success(mock_call_txt2img, client):
    mock_call_txt2img.return_value = ([DUMMY_IMAGE_B64], 12345)

    payload = {"prompt": "A test prompt"}
    response = client.post("/generate", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["image_base64"] == DUMMY_IMAGE_B64
    assert data["seed"] == 12345
    assert "generation_time" in data

@patch("main.call_txt2img")
def test_generate_failure_no_images(mock_call_txt2img, client):
    mock_call_txt2img.return_value = ([], -1)

    payload = {"prompt": "A failing prompt"}
    response = client.post("/generate", json=payload)
    
    assert response.status_code == 500
    assert response.json()["detail"] == "sd-server returned no images"

@patch("main.call_txt2img")
def test_generate_file_success(mock_call_txt2img, client):
    mock_call_txt2img.return_value = ([DUMMY_IMAGE_B64], 12345)
    
    payload = {"prompt": "file prompt"}
    response = client.post("/generate/file", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "filename" in data
    assert "path" in data
    assert data["seed"] == 12345

    filepath = OUTPUT_DIR / data["filename"]
    assert filepath.exists()
    assert filepath.read_bytes() == base64.b64decode(DUMMY_IMAGE_B64)
