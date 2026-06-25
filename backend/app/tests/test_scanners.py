"""Unit tests for the pure scanner functions — no DB, no network mocking needed
for the scoring logic itself."""

from app.scanner.cookies import scan_cookies


def test_cookies_no_cookies_is_full_score(monkeypatch):
    """A site that sets no cookies has no cookie-risk surface → 100."""
    class FakeResponse:
        headers = type("H", (), {"get_list": lambda self, k: []})()

    import app.scanner.cookies as cookies_mod
    monkeypatch.setattr(cookies_mod.httpx, "get", lambda *a, **k: FakeResponse())

    result = scan_cookies("https://example.com")
    assert result["score"] == 100
    assert result["unreachable"] is False


def test_cookies_unreachable_flag(monkeypatch):
    """A site we can't reach is flagged unreachable, not scored 0 as a finding."""
    import app.scanner.cookies as cookies_mod
    import httpx

    def boom(*a, **k):
        raise httpx.RequestError("nope")

    monkeypatch.setattr(cookies_mod.httpx, "get", boom)

    result = scan_cookies("https://unreachable.invalid")
    assert result["unreachable"] is True
    assert result["score"] == 0