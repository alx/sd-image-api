import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Override OUTPUT_DIR for tests before importing main
os.environ["OUTPUT_DIR"] = "./test_outputs"

from main import app, OUTPUT_DIR

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    # Setup test outputs directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Teardown test outputs directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
