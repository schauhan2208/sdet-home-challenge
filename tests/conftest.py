import threading

import pytest

from app.server import make_server

CREDS = {"admin": "s3cret"}


def start(tmp_path, credentials=None, name="db.sqlite"):
    srv = make_server(port=0, db_path=str(tmp_path / name), credentials=credentials)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture
def server_url(tmp_path):
    srv, url = start(tmp_path)
    yield url
    srv.shutdown(); srv.server_close()


@pytest.fixture
def auth_server_url(tmp_path):
    srv, url = start(tmp_path, CREDS)
    yield url
    srv.shutdown(); srv.server_close()
