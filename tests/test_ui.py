"""Playwright UI tests (run with: pytest -m ui). Needs `playwright install chromium`."""
import pytest
import requests
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui

SENSITIVE = {
    "[REDACTED_JWT]": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123_-",
    "[REDACTED_EMAIL]": "jane.doe@example.com",
    "[REDACTED_IP]": "172.16.254.1",
    "[REDACTED_CARD]": "4111 1111 1111 1111",
}


def test_page_shows_redacted_values_only(page: Page, server_url):
    for raw in SENSITIVE.values():
        requests.post(f"{server_url}/messages", json={"message": f"data: {raw}"})
    page.goto(server_url)
    rows = page.locator("#messages tbody tr")
    expect(rows).to_have_count(len(SENSITIVE))
    body = page.locator("#messages").inner_text()
    for placeholder, raw in SENSITIVE.items():
        assert placeholder in body
        assert raw not in body


def test_page_escapes_html(page: Page, server_url):
    requests.post(f"{server_url}/messages", json={"message": "<b>bold</b>"})
    page.goto(server_url)
    expect(page.locator("td.msg")).to_have_text("<b>bold</b>")
    assert page.locator("td.msg b").count() == 0


def test_page_requires_auth(browser, auth_server_url):
    anon = browser.new_context()
    assert anon.new_page().goto(auth_server_url).status == 401
    ctx = browser.new_context(http_credentials={"username": "admin", "password": "s3cret"})
    p = ctx.new_page()
    assert p.goto(auth_server_url).status == 200
    expect(p.locator("h1")).to_have_text("Messages")
