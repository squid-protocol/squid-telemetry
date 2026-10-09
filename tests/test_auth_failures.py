import os, sys
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TRAFFIC_READ_PAT", "test-token")
import scraper


def _resp(status, text="", headers=None, body=None):
    r = mock.Mock(status_code=status, text=text, headers=headers or {})
    r.json.return_value = body if body is not None else []
    return r


def test_auth_failures_recorded_rate_limits_ignored():
    scraper.AUTH_FAILURES.clear()
    scraper._note_auth_failure(_resp(401, "Bad credentials"), "views")
    scraper._note_auth_failure(_resp(403, "Resource not accessible"), "clones")
    scraper._note_auth_failure(_resp(403, "API rate limit exceeded"), "paths")
    scraper._note_auth_failure(_resp(403, "", {"x-ratelimit-remaining": "0"}), "refs")
    scraper._note_auth_failure(_resp(404), "missing")
    assert scraper.AUTH_FAILURES == ["views: HTTP 401", "clones: HTTP 403"]


def test_failed_page_returns_none_not_empty_list():
    scraper.AUTH_FAILURES.clear()
    with mock.patch.object(scraper.requests, "get",
                           return_value=_resp(403, "Resource not accessible by personal access token")):
        assert scraper._fetch_all_pages("https://api.github.com/x/stargazers", scraper.HEADERS) is None
    assert scraper.AUTH_FAILURES == ["https://api.github.com/x/stargazers: HTTP 403"]
