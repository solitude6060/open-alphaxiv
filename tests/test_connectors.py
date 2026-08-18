from __future__ import annotations

import httpx
import pytest

from app.connectors.arxiv import IntervalLimiter, list_category, search_arxiv
from app.connectors.semantic_scholar import build_graph_from_s2, validate_s2_url


ATOM_FEED = """
<feed>
  <entry>
    <id>http://arxiv.org/abs/2201.08239v1</id>
    <title>Attention Is All You Need</title>
    <summary>Transformer abstract.</summary>
    <published>2017-06-12T00:00:00Z</published>
    <author><name>Ashish Vaswani</name></author>
  </entry>
</feed>
"""


def test_arxiv_limiter_sleeps_inside_three_second_window() -> None:
    sleeps: list[float] = []

    class Clock:
        def __init__(self) -> None:
            self.t = 0.0

        def monotonic(self) -> float:
            return self.t

        def sleep(self, seconds: float) -> None:
            sleeps.append(seconds)
            self.t += seconds

    clock = Clock()
    limiter = IntervalLimiter(min_interval_s=3.0, clock=clock.monotonic, sleeper=clock.sleep)
    limiter.wait()
    clock.t += 0.5
    limiter.wait()
    assert sleeps == [2.5]


def test_list_category_calls_export_arxiv_org(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_fetch(url: str, timeout: float = 8.0) -> str:
        captured["url"] = url
        return ATOM_FEED

    monkeypatch.setattr("app.connectors.arxiv.fetch_text", fake_fetch)
    monkeypatch.setattr("app.connectors.arxiv.ARXIV_LIMITER", IntervalLimiter(min_interval_s=0, clock=lambda: 0.0, sleeper=lambda _s: None))
    rows = list_category("cs.LG", max_results=10)
    assert "export.arxiv.org" in captured["url"]
    assert "cat:cs.LG" in captured["url"]
    assert "alphaxiv.org" not in captured["url"]
    assert rows[0]["arxiv_id"] == "2201.08239"
    assert rows[0]["landing_url"] == "https://arxiv.org/abs/2201.08239"


def test_search_arxiv_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query"):
        search_arxiv("  ")


def test_fetch_text_rejects_non_arxiv_hosts() -> None:
    from app.connectors.arxiv import fetch_text

    with pytest.raises(ValueError, match="export.arxiv.org"):
        fetch_text("https://alphaxiv.org/api/query")


def test_s2_url_rejects_link_local() -> None:
    with pytest.raises(ValueError, match="semanticscholar"):
        validate_s2_url("http://169.254.169.254/graph/v1/paper/x")


def test_build_graph_from_s2_classifies_prior_and_derivative() -> None:
    seed = {
        "paperId": "seed-id",
        "title": "Attention Is All You Need",
        "year": 2017,
        "citationCount": 100,
        "url": "https://www.semanticscholar.org/paper/seed",
        "externalIds": {"ArXiv": "1706.03762"},
        "authors": [{"name": "Ashish Vaswani"}],
    }
    references = [
        {
            "citedPaper": {
                "paperId": "prior-id",
                "title": "Neural Machine Translation by Jointly Learning to Align and Translate",
                "year": 2014,
                "citationCount": 10,
                "url": "https://www.semanticscholar.org/paper/prior",
                "externalIds": {},
                "authors": [{"name": "Dzmitry Bahdanau"}],
            }
        }
    ]
    citations = [
        {
            "citingPaper": {
                "paperId": "later-id",
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "year": 2019,
                "citationCount": 20,
                "url": "https://www.semanticscholar.org/paper/later",
                "externalIds": {"ArXiv": "1810.04805"},
                "authors": [{"name": "Jacob Devlin"}],
            }
        }
    ]
    graph = build_graph_from_s2(seed, references, citations)
    titles = {node["title"] for node in graph["nodes"]}
    assert "Prior work 1:" not in " ".join(titles)
    assert "Attention Is All You Need" in titles
    assert "Neural Machine Translation by Jointly Learning to Align and Translate" in titles
    assert "BERT: Pre-training of Deep Bidirectional Transformers" in titles
    groups = {node["external_id"]: node["group"] for node in graph["nodes"]}
    assert groups["seed-id"] == "seed"
    assert groups["prior-id"] == "prior"
    assert groups["later-id"] == "derivative"
    assert graph["attribution"] == "Data from Semantic Scholar"


def test_request_s2_json_retries_once_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.connectors.semantic_scholar import request_s2_json

    sleeps: list[float] = []
    calls = {"n": 0}

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
            self.status_code = status_code
            self.headers = {"Retry-After": "1"}
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/x")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError("429", request=request, response=response)

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResponse:
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeResponse(429)
            return FakeResponse(200, {"paperId": "seed-id", "title": "Attention Is All You Need"})

    monkeypatch.setattr("app.connectors.semantic_scholar.httpx.Client", FakeClient)
    payload = request_s2_json(
        "https://api.semanticscholar.org/graph/v1/paper/ARXIV:1706.03762",
        sleeper=lambda seconds: sleeps.append(seconds),
    )
    assert calls["n"] == 2
    assert sleeps == [1.0]
    assert payload["title"] == "Attention Is All You Need"


def test_request_s2_json_exhausted_429_mentions_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.connectors.semantic_scholar import request_s2_json

    class FakeResponse:
        status_code = 429
        headers = {"Retry-After": "0"}

        def raise_for_status(self) -> None:
            raise AssertionError("raise_for_status should not run after 429 exhaustion")

        def json(self) -> dict[str, object]:
            return {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.connectors.semantic_scholar.httpx.Client", FakeClient)
    with pytest.raises(RuntimeError, match="SEMANTIC_SCHOLAR_API_KEY"):
        request_s2_json(
            "https://api.semanticscholar.org/graph/v1/paper/ARXIV:1706.03762",
            sleeper=lambda _seconds: None,
        )
