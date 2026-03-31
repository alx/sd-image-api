import pytest
from unittest.mock import patch
import base64
from main import jobs

DUMMY_IMAGE_B64 = base64.b64encode(b'dummy_image_data_png_here').decode('utf-8')

@patch("main.call_txt2img")
def test_generate_batch_and_poll_status(mock_call_txt2img, client):
    # Setup mock to succeed
    mock_call_txt2img.return_value = ([DUMMY_IMAGE_B64], 12345)
    
    payload = [
        {"prompt": "Item 1"},
        {"prompt": "Item 2"}
    ]
    
    # Create the background batch job
    response = client.post("/generate/batch", json=payload)
    assert response.status_code == 202
    data = response.json()
    
    job_id = data["job_id"]
    # With TestClient, background tasks execute immediately after the response is generated.
    # Therefore, the initial status might actually be queued in the response, but finished by the time we check again.
    assert data["total"] == 2
    
    # Poll job status
    poll_response = client.get(f"/jobs/{job_id}")
    assert poll_response.status_code == 200
    poll_data = poll_response.json()
    assert poll_data["job_id"] == job_id
    
    # It should have finished processing
    assert poll_data["status"] == "completed"
    assert poll_data["progress"] == 2
    assert poll_data["total"] == 2
    assert len(poll_data["results"]) == 2
    assert len(poll_data["errors"]) == 0

def test_get_job_not_found(client):
    response = client.get("/jobs/nonexistent_id")
    assert response.status_code == 404
