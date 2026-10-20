import shutil
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.job_store import job_store


@pytest.fixture(autouse=True)
async def reset_job_store_and_storage(tmp_path: Path, monkeypatch):
    """Fixture to ensure a clean in-memory job store and temporary storage directory

    for every test run.
    """
    test_storage = tmp_path / "test_storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "STORAGE_DIR", test_storage)

    # Clear in-memory job store
    await job_store.clear()

    yield

    # Teardown: clear store and temp files
    await job_store.clear()
    if test_storage.exists():
        shutil.rmtree(test_storage, ignore_errors=True)


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
