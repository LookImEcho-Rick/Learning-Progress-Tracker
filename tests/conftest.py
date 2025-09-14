import os
import shutil
import tempfile
import importlib
import pytest
import sys


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    # Ensure project root is importable
    root = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(root)
    if root not in sys.path:
        sys.path.insert(0, root)

    tmpdir = tempfile.mkdtemp()
    data_dir = os.path.join(tmpdir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # Reload storage to ensure fresh state and patch DB_PATH
    storage = importlib.import_module("services.storage")
    monkeypatch.setattr(storage, "DB_PATH", os.path.join(data_dir, "tracker.db"), raising=False)

    yield
    shutil.rmtree(tmpdir, ignore_errors=True)
