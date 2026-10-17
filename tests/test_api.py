import requests
# ---- auth: CLI and process-level (env vars) coverage
import os
import socket
import subprocess
import sys
import time
from client.msgclient import MessageClient
from tests.conftest import CREDS, start


def test_post_and_get(server_url):
    r = requests.post(f"{server_url}/messages", json={"message": "hi"})
    assert r.status_code == 201
    body = r.json()
    assert body["message"] == "hi" and isinstance(body["id"], int)
    assert requests.get(f"{server_url}/messages").json() == [body]


def test_redacted_before_storage_and_in_response(server_url):
    r = requests.post(f"{server_url}/messages", json={"message": "mail me a@b.io from 10.1.2.3"})
    assert r.json()["message"] == "mail me [REDACTED_EMAIL] from [REDACTED_IP]"
    stored = requests.get(f"{server_url}/messages").json()[0]["message"]
    assert "a@b.io" not in stored and "10.1.2.3" not in stored


def test_validation_errors(server_url):
    for payload in ({}, {"message": ""}, {"message": "  "}, {"message": 5}, [1]):
        assert requests.post(f"{server_url}/messages", json=payload).status_code == 400
    r = requests.post(f"{server_url}/messages", data="not json",
                      headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_payload_too_large(server_url):
    r = requests.post(f"{server_url}/messages", json={"message": "x" * 70_000})
    assert r.status_code == 413


def test_delete(server_url):
    mid = requests.post(f"{server_url}/messages", json={"message": "bye"}).json()["id"]
    assert requests.delete(f"{server_url}/messages/{mid}").status_code == 204
    assert requests.get(f"{server_url}/messages").json() == []
    assert requests.delete(f"{server_url}/messages/{mid}").status_code == 404


def test_unknown_route(server_url):
    assert requests.get(f"{server_url}/nope").status_code == 404


def test_auth_required(auth_server_url):
    assert requests.get(f"{auth_server_url}/health").status_code == 200
    r = requests.get(f"{auth_server_url}/messages")
    assert r.status_code == 401 and "Basic" in r.headers["WWW-Authenticate"]
    assert requests.post(f"{auth_server_url}/messages", json={"message": "x"}).status_code == 401
    assert requests.get(f"{auth_server_url}/messages", auth=("admin", "wrong")).status_code == 401
    assert requests.get(f"{auth_server_url}/messages", auth=("admin", "s3cret")).status_code == 200


def test_persistence_across_restart(tmp_path):
    srv, url = start(tmp_path, name="p.sqlite")
    requests.post(f"{url}/messages", json={"message": "keep me"})
    srv.shutdown(); srv.server_close()
    srv2, url2 = start(tmp_path, name="p.sqlite")
    try:
        assert [m["message"] for m in requests.get(f"{url2}/messages").json()] == ["keep me"]
    finally:
        srv2.shutdown(); srv2.server_close()


def test_client_library_roundtrip(auth_server_url):
    c = MessageClient(auth_server_url, "admin", "s3cret")
    sent = c.send("from client 1.1.1.1")
    assert sent["message"] == "from client [REDACTED_IP]"
    assert c.list() == [sent]
    c.delete(sent["id"])
    assert c.list() == []


def test_client_cli(server_url, capsys):
    from client.msgclient import main
    assert main(["--url",server_url, "send", "hello a@b.io"]) == 0
    assert main(["--url", server_url, "list", "--json"]) == 0
    assert "[REDACTED_EMAIL]" in capsys.readouterr().out


def test_cli_without_credentials_fails(auth_server_url, capsys):
    from client.msgclient import main
    assert main(["--url", auth_server_url, "list"]) == 1
    assert "401" in capsys.readouterr().err


def test_cli_with_credentials(auth_server_url, capsys):
    from client.msgclient import main
    creds = ["--user", "admin", "--password", "s3cret"]
    assert main(["--url", auth_server_url, *creds, "send", "auth test a@b.io"]) == 0
    assert main(["--url", auth_server_url, *creds, "list"]) == 0
    assert "auth test [REDACTED_EMAIL]" in capsys.readouterr().out
