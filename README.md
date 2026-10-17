# SDET Home Challenge: Message Server

Python HTTP server that accepts messages, **redacts sensitive data before storage**, and shows them in a table. Includes a client/CLI, Docker packaging, and API + Playwright tests.

Bonus items done: SQLite persistence, Basic auth, TLS (self-signed), DELETE.

## Run the server

```bash
docker build -t msg-server .
docker run -p 8000:8000 -v msgdata:/data msg-server          # open http://localhost:8000 (auth=off)
docker run -p 8000:8000 -v msgdata:/data -e AUTH_USER=admin -e AUTH_PASS=secret msg-server    # open http://localhost:8000 (auth=on)
```

Optional env vars: `AUTH_USER` + `AUTH_PASS` (enable Basic auth), `TLS_CERT` + `TLS_KEY` (enable HTTPS), `DB_PATH`, `PORT`.

```bash
# auth + TLS
sh certs/gen_cert.sh
docker run -p 8443:8000 -v "$PWD/certs:/certs" -e AUTH_USER=admin -e AUTH_PASS=secret \
  -e TLS_CERT=/certs/cert.pem -e TLS_KEY=/certs/key.pem msg-server

docker run -p 8443:8000 -v msgdata:/data -v "${PWD}/certs:/certs" -e TLS_CERT=/certs/cert.pem -e TLS_KEY=/certs/key.pem msg-server   # (auth=off)
docker run -p 8443:8000 -v msgdata:/data -v "${PWD}/certs:/certs" -e TLS_CERT=/certs/cert.pem -e TLS_KEY=/certs/key.pem -e AUTH_USER=admin -e AUTH_PASS=secret msg-server  # Auth credentials provided (auth=on)
```

Without Docker: `pip install -r requirements.txt && python -m app.server`.

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/messages` | body `{"message": "..."}` → 201 with stored (redacted) message |
| GET | `/messages` | JSON list |
| DELETE | `/messages/{id}` | 204 / 404 |
| GET | `/` | HTML table |
| GET | `/health` | always unauthenticated |

## Client / CLI

```bash
python -m client.msgclient send "contact me at a@b.io"   # Send a message
python -m client.msgclient list       # Tabular format
python -m client.msgclient list --json  # Json Format
python -m client.msgclient delete 1      # delete a message
# env: MSG_URL, MSG_USER, MSG_PASS; add --insecure for self-signed TLS
```

In automation: `from client.msgclient import MessageClient`.

## Tests

```bash
pip install -r requirements-dev.txt
playwright install chromium
pytest                # everything
pytest -m "not ui"    # redaction + API only (no browser)
pytest -m ui          # Playwright only
# added this into pytest.ini '--html=reports/report.html --self-contained-html'  to Generate html test execution report 
```

Tests start the server in-process on a random port with a temp SQLite file, so no Docker is needed.

## Redaction rules

JWTs (`eyJ...x.y.z`), emails, IPv4 (octets validated 0-255), credit cards (13-19 digits, optional space/hyphen grouping, **Luhn-checked** to avoid masking random numbers). Replaced with `[REDACTED_JWT|EMAIL|IP|CARD]`.

## Difficulties

- Pattern collisions: a failed card match could swallow the tail of an IP address. Fixed by running IP redaction first and using strict card group formats.
- Avoiding false positives (version strings like `1.2.3`, invalid IPs, non-Luhn digit runs) without missing real data.


## Self-assessed room for improvement

- Stdlib `http.server` is fine for a demo as need to create simple Python HTTP Server. Python frameworks can be used for production.
- Auth is a single shared Basic credential in env vars; no hashing, rotation, or per-user roles.
- Redaction is irreversible by design, so there is no audit of what was masked.
- No pagination on `GET /messages`; the page re-renders the whole table.
- CI (GitHub Actions running tests) is not set up.