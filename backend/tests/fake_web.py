"""An in-memory fake web for URL import tests. No real network access happens in tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from app.adapters.web_fetch import SafeFetcher

PUBLIC_TEST_IP = "93.184.216.34"


@dataclass
class FakeWeb:
    pages: dict[str, httpx.Response] = field(default_factory=dict)
    dns: dict[str, list[str]] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)
    robots_requests: list[str] = field(default_factory=list)
    robots: dict[str, httpx.Response] = field(default_factory=dict)
    request_headers: list[httpx.Headers] = field(default_factory=list)

    def add_robots(self, origin: str, text: str | None = None, status: int = 200) -> None:
        self.robots[f"{origin}/robots.txt"] = httpx.Response(
            status, headers={"content-type": "text/plain"}, content=(text or "").encode("utf-8")
        )

    def add_html(self, url: str, html: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
        self.pages[url] = httpx.Response(status, headers={"content-type": content_type}, content=html.encode("utf-8"))

    def add_redirect(self, url: str, location: str, status: int = 302) -> None:
        self.pages[url] = httpx.Response(status, headers={"location": location})

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.url.path == "/robots.txt":
            self.robots_requests.append(url)
            robots = self.robots.get(url)
            if robots is None:
                return httpx.Response(404, content=b"")  # no robots.txt: unrestricted
            return httpx.Response(robots.status_code, headers=robots.headers, content=robots.content)
        self.requests.append(url)
        self.request_headers.append(request.headers)
        response = self.pages.get(url)
        if response is None:
            return httpx.Response(404, headers={"content-type": "text/html"}, content=b"not found")
        return httpx.Response(response.status_code, headers=response.headers, content=response.content)

    def resolver(self, host: str) -> list[str]:
        return self.dns.get(host, [PUBLIC_TEST_IP])

    def fetcher(self, **kwargs) -> SafeFetcher:  # noqa: ANN003
        return SafeFetcher(transport=httpx.MockTransport(self.handler), resolver=self.resolver, **kwargs)


def job_posting_page(posting: dict | list, extra_head: str = "") -> str:
    return (
        "<!doctype html><html><head><title>Synthetic job</title>"
        f"{extra_head}"
        f'<script type="application/ld+json">{json.dumps(posting)}</script>'
        "</head><body><h1>Visible page text is ignored</h1></body></html>"
    )


def synthetic_posting(**overrides) -> dict:  # noqa: ANN003
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Ohjelmistokehittäjä (synthetic)",
        "hiringOrganization": {"@type": "Organization", "name": "Esimerkki Oy"},
        "description": "<p>Synthetic role.</p><ul><li>Python</li><li>SQL</li></ul>",
        "datePosted": "2026-11-01",
        "validThrough": "2026-11-30T23:59:00+02:00",
        "employmentType": "FULL_TIME",
        "jobLocation": {
            "@type": "Place",
            "address": {"addressLocality": "Turku", "addressRegion": "Varsinais-Suomi", "addressCountry": "FI"},
        },
        "baseSalary": {
            "@type": "MonetaryAmount",
            "currency": "EUR",
            "value": {"@type": "QuantitativeValue", "minValue": 3500, "maxValue": 4200, "unitText": "MONTH"},
        },
        "identifier": {"@type": "PropertyValue", "name": "Esimerkki Oy", "value": "JOB-123"},
        "inLanguage": "fi",
    }
    posting.update(overrides)
    return {k: v for k, v in posting.items() if v is not None}
