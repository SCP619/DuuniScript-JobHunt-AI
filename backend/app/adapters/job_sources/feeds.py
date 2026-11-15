"""Official job feeds and public job APIs (AFD 4: permitted sources only).

Each site here publishes its jobs for programmatic use, and its terms were checked on
2026-11-10 (docs/SOURCE_EVALUATION.md). The rules we follow for all of them:

- read only the published feed or API, at most as often as the site asks (``min_interval_hours``);
- keep the link to the original posting and show the site as the source (attribution);
- never pass the jobs on to anyone else; they are only shown to the one local user;
- robots.txt is honoured, except where the site's own API documentation tells programs to
  call an address that its robots.txt (written for crawlers) lists (``honour_robots=False``).

Parsers are pure functions from the response body to ``FeedJob`` records. Feed content is
untrusted: HTML is reduced to plain text, nothing is executed, and fields are length-limited.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from app.adapters.job_sources.jsonld import html_to_text
from app.adapters.job_sources.language import detect_language
from app.services import eligibility

PARSER_VERSION = "feeds-1"
MAX_DESCRIPTION_CHARS = 100_000
HELSINKI = ZoneInfo("Europe/Helsinki")
_FLAGS = re.compile("[\U0001f1e6-\U0001f1ff]")


class FeedFormatError(Exception):
    """The response was not the feed format this site publishes."""


@dataclass
class FeedJob:
    external_id: str
    link: str
    title: str
    company: str
    description: str | None = None
    location: str | None = None
    employment_type: str | None = None
    work_mode: str | None = None
    salary_text: str | None = None
    published_on: date | None = None
    deadline_on: date | None = None
    deadline_at: datetime | None = None
    language: str | None = None
    available_from_finland: str = eligibility.UNKNOWN
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeedSite:
    key: str
    name: str
    domain: str
    urls: tuple[str, ...]
    parse: Callable[[bytes], list[FeedJob]]
    min_interval_hours: float
    terms_url: str
    access_type: str  # official_api or official_feed
    access_method: str
    attribution: str
    honour_robots: bool = True


# ---------- Small helpers ----------


def _text(value: Any, limit: int = 300) -> str | None:
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    cleaned = " ".join(html.unescape(str(value)).split())
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = " ".join(_FLAGS.sub("", cleaned).split())
    return cleaned[:limit] or None


def _description(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = html_to_text(value)
    return text[:MAX_DESCRIPTION_CHARS] if text else None


def _http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    parts = urlsplit(value)
    return value[:2000] if parts.scheme in ("http", "https") and parts.netloc else None


def _on_site(url: str | None, domain: str) -> str | None:
    """Links must stay on the publishing site's own domain."""
    if not url:
        return None
    host = (urlsplit(url).hostname or "").lower()
    return url if host == domain or host.endswith("." + domain) else None


_EMPLOYMENT = [
    (re.compile(r"intern|trainee|praktikum|harjoittel"), "internship"),
    (re.compile(r"part[ _-]?time|teilzeit|osa-aika|werkstudent"), "part_time"),
    (re.compile(r"full[ _-]?time|vollzeit|kokoaika|permanent|festanstellung"), "full_time"),
    (re.compile(r"contract|freelance|freelancer|contractor|consult"), "contract"),
    (re.compile(r"temporary|temp\b|befristet|määräaika"), "temporary"),
    (re.compile(r"volunteer"), "volunteer"),
]


def _employment(*values: Any) -> str | None:
    words: list[str] = []
    for value in values:
        if isinstance(value, list):
            words += [str(v) for v in value if isinstance(v, (str, int))]
        elif isinstance(value, str):
            words.append(value)
    found = []
    for word in words:
        for pattern, kind in _EMPLOYMENT:
            if pattern.search(word.lower()):
                found.append(kind)
                break
    unique = list(dict.fromkeys(found))
    return unique[0] if len(unique) == 1 else None


def _rss_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError):
        return None


def _iso_date(value: Any) -> date | None:
    if isinstance(value, str):
        match = re.match(r"\s*(\d{4}-\d{2}-\d{2})", value)
        if match:
            try:
                return date.fromisoformat(match.group(1))
            except ValueError:
                return None
    return None


def _epoch_date(value: Any) -> date | None:
    try:
        seconds = int(str(value))
    except (TypeError, ValueError):
        return None
    if not 946_684_800 <= seconds <= 4_102_444_800:  # 2000..2100
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).date()


def _load_json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise FeedFormatError("not_json") from exc


def _load_rss_items(body: bytes) -> list[ET.Element]:
    if b"<!DOCTYPE" in body[:2000].upper() or b"<!ENTITY" in body.upper():
        raise FeedFormatError("dtd_not_allowed")  # no entity expansion from feeds
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FeedFormatError("not_xml") from exc
    return [el for el in root.iter() if _local(el.tag) == "item"]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(item: ET.Element, *names: str) -> str | None:
    for name in names:
        for el in item:
            if _local(el.tag) == name and el.text and el.text.strip():
                return el.text.strip()
    return None


def _finish(job: FeedJob) -> FeedJob:
    job.title = job.title[:300]
    job.company = job.company[:300]
    if job.language is None:
        job.language = detect_language(job.description)
    return job


def _salary_range(low: Any, high: Any, currency: Any, period: Any = None) -> str | None:
    def num(value: Any) -> str | None:
        try:
            amount = float(str(value))
        except (TypeError, ValueError):
            return None
        return f"{amount:,.0f}".replace(",", " ") if amount > 0 else None

    low_s, high_s = num(low), num(high)
    if not low_s and not high_s:
        return None
    span = f"{low_s}–{high_s}" if low_s and high_s and low_s != high_s else (low_s or high_s)
    periods = {"annual": "per year", "yearly": "per year", "monthly": "per month", "weekly": "per week",
               "fortnightly": "per two weeks", "hourly": "per hour", "daily": "per day"}
    per = periods.get(period.lower()) if isinstance(period, str) else None
    parts = [span, _text(currency, 10), per]
    return " ".join(p for p in parts if p)[:300]


# ---------- Remotive (public API) ----------


def parse_remotive(body: bytes) -> list[FeedJob]:
    data = _load_json(body)
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise FeedFormatError("unexpected_shape")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        link = _on_site(_http_url(item.get("url")), "remotive.com")
        title, company = _text(item.get("title")), _text(item.get("company_name"))
        if not (link and title and company and item.get("id")):
            continue
        location = _text(item.get("candidate_required_location"))
        jobs.append(_finish(FeedJob(
            external_id=str(item["id"])[:100],
            link=link,
            title=title,
            company=company,
            description=_description(item.get("description")),
            location=location,
            employment_type=_employment(item.get("job_type")),
            work_mode="remote",
            salary_text=_text(item.get("salary")),
            published_on=_iso_date(item.get("publication_date")),
            available_from_finland=eligibility.from_text(location),
            raw={k: item.get(k) for k in ("id", "url", "title", "company_name", "category", "job_type",
                                          "publication_date", "candidate_required_location", "salary")},
        )))
    return jobs


# ---------- Jobspresso (WordPress job feed) ----------


def parse_jobspresso(body: bytes) -> list[FeedJob]:
    jobs = []
    for item in _load_rss_items(body):
        link = _on_site(_http_url(_child(item, "link")), "jobspresso.co")
        title = _text(_child(item, "title"))
        creator = _child(item, "creator") or ""
        company_part, _, place_part = creator.partition("<br>")
        company = _text(_child(item, "company")) or _text(company_part)
        guid = _child(item, "guid") or ""
        post_id = (parse_qs(urlsplit(html.unescape(guid)).query).get("p") or [None])[0] or link
        if not (link and title and company and post_id):
            continue
        location = _text(place_part.replace("⚲", " "))
        jobs.append(_finish(FeedJob(
            external_id=str(post_id)[:300],
            link=link,
            title=title,
            company=company,
            description=_description(_child(item, "encoded", "description")),
            location=location,
            employment_type=_employment(_child(item, "job_category"), _child(item, "job_type")),
            work_mode="remote",
            salary_text=_text(_child(item, "salary")),
            published_on=_rss_date(_child(item, "pubDate")),
            available_from_finland=eligibility.from_text(location),
            raw={"link": link, "title": title, "creator": _text(creator), "pubDate": _child(item, "pubDate"),
                 "job_type": _child(item, "job_type"), "job_category": _child(item, "job_category")},
        )))
    return jobs


# ---------- We Work Remotely (RSS) ----------


def parse_weworkremotely(body: bytes) -> list[FeedJob]:
    jobs = []
    for item in _load_rss_items(body):
        link = _on_site(_http_url(_child(item, "link")), "weworkremotely.com")
        heading = _text(_child(item, "title")) or ""
        company, sep, title = heading.partition(": ")
        if not sep:
            continue
        region, countries = _text(_child(item, "region")), _text(_child(item, "country"))
        if not (link and title and company):
            continue
        location = countries or region
        jobs.append(_finish(FeedJob(
            external_id=(_child(item, "guid") or link)[:300],
            link=link,
            title=title,
            company=company,
            description=_description(_child(item, "description")),
            location=location,
            employment_type=_employment(_child(item, "type")),
            work_mode="remote",
            published_on=_rss_date(_child(item, "pubDate")),
            available_from_finland=eligibility.from_text(location),
            raw={"link": link, "title": heading, "region": region, "country": countries,
                 "type": _child(item, "type"), "pubDate": _child(item, "pubDate")},
        )))
    return jobs


# ---------- Himalayas (public API, search for jobs open to Finland) ----------


def parse_himalayas(body: bytes) -> list[FeedJob]:
    data = _load_json(body)
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise FeedFormatError("unexpected_shape")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        link = _on_site(_http_url(item.get("guid")), "himalayas.app")
        title, company = _text(item.get("title")), _text(item.get("companyName"))
        if not (link and title and company):
            continue
        countries = [c for c in item.get("locationRestrictions") or [] if isinstance(c, str)]
        offsets = item.get("timezoneRestrictions") or []
        jobs.append(_finish(FeedJob(
            external_id=link,
            link=link,
            title=title,
            company=company,
            description=_description(item.get("description")),
            location=_text(", ".join(countries)) if countries else "Worldwide",
            employment_type=_employment(item.get("employmentType")),
            work_mode="remote",
            salary_text=_salary_range(item.get("minSalary"), item.get("maxSalary"), item.get("currency"),
                                      item.get("salaryPeriod")),
            published_on=_epoch_date(item.get("pubDate")),
            available_from_finland=eligibility.from_restrictions(countries, offsets),
            raw={k: item.get(k) for k in ("guid", "title", "companyName", "employmentType", "locationRestrictions",
                                          "timezoneRestrictions", "pubDate", "expiryDate")},
        )))
    return jobs


# ---------- Jobicy (public API, jobs open to Finland and to Europe) ----------


def parse_jobicy(body: bytes) -> list[FeedJob]:
    data = _load_json(body)
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise FeedFormatError("unexpected_shape")
    jobs = []
    for item in data["jobs"]:
        if not isinstance(item, dict):
            continue
        link = _on_site(_http_url(item.get("url")), "jobicy.com")
        title, company = _text(item.get("jobTitle")), _text(item.get("companyName"))
        if not (link and title and company and item.get("id")):
            continue
        location = _text(item.get("jobGeo"))
        jobs.append(_finish(FeedJob(
            external_id=str(item["id"])[:100],
            link=link,
            title=title,
            company=company,
            description=_description(item.get("jobDescription")),
            location=location,
            employment_type=_employment(item.get("jobType")),
            work_mode="remote",
            salary_text=_salary_range(item.get("salaryMin") or item.get("annualSalaryMin"),
                                      item.get("salaryMax") or item.get("annualSalaryMax"),
                                      item.get("salaryCurrency"), item.get("salaryPeriod")),
            published_on=_iso_date(item.get("pubDate")),
            available_from_finland=eligibility.from_text(location),
            raw={k: item.get(k) for k in ("id", "url", "jobTitle", "companyName", "jobGeo", "jobType", "pubDate")},
        )))
    return jobs


# ---------- Arbeitnow (public API; remote jobs only) ----------


def parse_arbeitnow(body: bytes) -> list[FeedJob]:
    data = _load_json(body)
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise FeedFormatError("unexpected_shape")
    jobs = []
    for item in data["data"]:
        if not isinstance(item, dict) or item.get("remote") is not True:
            continue  # the board is mostly on-site jobs in Germany
        link = _on_site(_http_url(item.get("url")), "arbeitnow.com")
        title, company = _text(item.get("title")), _text(item.get("company_name"))
        if not (link and title and company and item.get("slug")):
            continue
        location = _text(item.get("location"))
        jobs.append(_finish(FeedJob(
            external_id=str(item["slug"])[:300],
            link=link,
            title=title,
            company=company,
            description=_description(item.get("description")),
            location=location,
            employment_type=_employment(item.get("job_types")),
            work_mode="remote",
            published_on=_epoch_date(item.get("created_at")),
            available_from_finland=eligibility.from_text(location),
            raw={k: item.get(k) for k in ("slug", "url", "title", "company_name", "location", "remote",
                                          "job_types", "created_at")},
        )))
    return jobs


# ---------- Åbo Akademi (official RSS, Laura recruitment system) ----------


def _helsinki_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=HELSINKI)
    except ValueError:
        return None


def parse_abo_akademi(body: bytes) -> list[FeedJob]:
    jobs = []
    for item in _load_rss_items(body):
        link = _on_site(_http_url(_child(item, "link")), "abo.rekrytointi.com")
        title = _text(_child(item, "title"))
        job_id = (parse_qs(urlsplit(link or "").query).get("jid") or [None])[0]
        if not (link and title and job_id):
            continue
        deadline = _helsinki_time(_child(item, "enddate"))
        start = _helsinki_time(_child(item, "startdate"))
        # The plain <description> only states the application period; the advertisement is
        # in the system's own namespaced description element.
        advert = next(
            (el.text for el in item if el.tag.startswith("{") and _local(el.tag) == "description" and el.text),
            None,
        )
        jobs.append(_finish(FeedJob(
            external_id=job_id[:100],
            link=link,
            title=title,
            company="Åbo Akademi",
            description=_description(advert),
            location="Turku (Åbo), Finland",
            published_on=start.date() if start else _rss_date(_child(item, "pubDate")),
            deadline_on=deadline.date() if deadline else None,
            deadline_at=deadline.astimezone(timezone.utc) if deadline else None,
            available_from_finland=eligibility.YES,
            raw={"link": link, "title": title, "startdate": _child(item, "startdate"),
                 "enddate": _child(item, "enddate"), "pubDate": _child(item, "pubDate")},
        )))
    return _dedupe(jobs)


def _dedupe(jobs: list[FeedJob]) -> list[FeedJob]:
    seen: set[str] = set()
    unique = []
    for job in jobs:
        if job.external_id not in seen:
            seen.add(job.external_id)
            unique.append(job)
    return unique


# ---------- The sites ----------

SITES: tuple[FeedSite, ...] = (
    FeedSite(
        key="feed_remotive", name="Remotive", domain="remotive.com",
        urls=("https://remotive.com/api/remote-jobs",),
        parse=parse_remotive, min_interval_hours=6, terms_url="https://remotive.com/api-documentation",
        access_type="official_api", access_method="Public remote jobs API",
        attribution="Jobs from Remotive. Each job links back to its Remotive page.",
        # Its robots.txt lists /api/* for crawlers, but its API documentation invites programs to
        # call this address (at most 4 times a day, with a link back), which is what we do.
        honour_robots=False,
    ),
    FeedSite(
        key="feed_jobspresso", name="Jobspresso", domain="jobspresso.co",
        urls=("https://jobspresso.co/feed/job_feed/",),
        parse=parse_jobspresso, min_interval_hours=2, terms_url="https://jobspresso.co/terms-and-conditions/",
        access_type="official_feed", access_method="Public job RSS feed",
        attribution="Jobs from Jobspresso. Each job links back to its Jobspresso page.",
    ),
    FeedSite(
        key="feed_weworkremotely", name="We Work Remotely", domain="weworkremotely.com",
        urls=("https://weworkremotely.com/remote-jobs.rss",),
        parse=parse_weworkremotely, min_interval_hours=2, terms_url="https://weworkremotely.com/terms-of-service",
        access_type="official_feed", access_method="Public job RSS feed",
        attribution="Jobs from We Work Remotely. Each job links back to its We Work Remotely page.",
    ),
    FeedSite(
        key="feed_himalayas", name="Himalayas", domain="himalayas.app",
        urls=("https://himalayas.app/jobs/api/search?country=Finland&sort=recent",),
        parse=parse_himalayas, min_interval_hours=6, terms_url="https://himalayas.app/api",
        access_type="official_api", access_method="Public jobs API (search, jobs open to Finland)",
        attribution="Jobs from Himalayas. Each job links back to its Himalayas page.",
    ),
    FeedSite(
        key="feed_jobicy", name="Jobicy", domain="jobicy.com",
        urls=("https://jobicy.com/api/jobs?count=100&geo=finland", "https://jobicy.com/api/jobs?count=100&geo=europe"),
        parse=parse_jobicy, min_interval_hours=6, terms_url="https://jobicy.com/jobs-rss-feed",
        access_type="official_api", access_method="Public remote jobs API (Finland and Europe)",
        attribution="Jobs from Jobicy. Each job links back to its Jobicy page.",
    ),
    FeedSite(
        key="feed_arbeitnow", name="Arbeitnow", domain="arbeitnow.com",
        urls=("https://www.arbeitnow.com/api/job-board-api",),
        parse=parse_arbeitnow, min_interval_hours=6, terms_url="https://www.arbeitnow.com/api/job-board-api",
        access_type="official_api", access_method="Public job board API (remote jobs only)",
        attribution="Jobs from Arbeitnow. Each job links back to its Arbeitnow page.",
    ),
    FeedSite(
        key="feed_abo_akademi", name="Åbo Akademi", domain="abo.rekrytointi.com",
        urls=("https://abo.rekrytointi.com/paikat/?o=A_RSS&jgid=1",),
        parse=parse_abo_akademi, min_interval_hours=2, terms_url="https://abo.rekrytointi.com/paikat/?o=A_LOJ&list=1",
        access_type="official_feed", access_method="Official vacancies RSS feed",
        attribution="Vacancies from Åbo Akademi's recruitment site. Each job links back to it.",
    ),
)
SITES_BY_KEY = {site.key: site for site in SITES}
