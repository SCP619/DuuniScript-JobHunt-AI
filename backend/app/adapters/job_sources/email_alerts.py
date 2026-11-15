"""Job alert emails -> job cards.

Job sites email their own alerts to the user; DuuniScript reads only those emails, never the
sites. Each card gives what the email states: title, company, location, the link and, for
some sites, how old the posting is. The description is not in alert emails.

Safety rules:
- Only emails from a known job site are read, and Gmail's DKIM check for that site must pass,
  so a look-alike email cannot add jobs.
- Only links on the site's own domain become jobs. Tracking and sign-in tokens are dropped
  where the clean posting address is known.
- Email content is untrusted text: it is stored and displayed, never executed or obeyed.

Formats marked ``verified`` were checked against real alert emails (LinkedIn and Glassdoor,
2026-11-10). The others follow each site's posting address pattern and fall back to the link
text; they are confirmed when a real alert from that site has been seen.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

PARSER_VERSION = "email-alert-1"
MAX_EMAIL_BYTES = 5 * 1024 * 1024
MAX_JOBS_PER_EMAIL = 100
FIELD_MAX = 300


@dataclass(frozen=True)
class AlertSite:
    key: str  # job_source.key
    name: str
    sender_domains: tuple[str, ...]
    link: re.Pattern[str]  # a posting link on the site's own domain; group 1 is the posting ID
    canonical: str | None  # "{id}" template, "path" (the link without its query) or None (as sent)
    order: tuple[str, ...] = ("title", "company", "location")
    verified: bool = False


def _site(key: str, name: str, domains: tuple[str, ...], link: str, canonical: str | None, **kw) -> AlertSite:  # noqa: ANN003
    return AlertSite(key, name, domains, re.compile(link, re.IGNORECASE), canonical, **kw)


SITES: tuple[AlertSite, ...] = (
    _site(
        "alert_linkedin", "LinkedIn job alerts", ("linkedin.com",),
        r"^https://(?:www\.|[a-z]{2}\.)?linkedin\.com/(?:comm/)?jobs/view/(?:[^/?#]*-)?(\d+)",
        "https://www.linkedin.com/jobs/view/{id}/", verified=True,
    ),
    _site(
        "alert_glassdoor", "Glassdoor job alerts", ("glassdoor.com", "glassdoor.fi", "glassdoor.co.uk", "glassdoor.de"),
        r"^https://(?:www\.)?glassdoor\.[a-z.]+/[^#]*?[?&]jobListingId=(\d+)",
        None, order=("company", "title", "location"), verified=True,
    ),
    _site(
        "alert_duunitori", "Duunitori job alerts", ("duunitori.fi",),
        r"^https://(?:www\.)?duunitori\.fi/tyopaikat/tyo/([\w-]+)", "https://duunitori.fi/tyopaikat/tyo/{id}",
    ),
    _site(
        "alert_jobly", "Jobly job alerts", ("jobly.fi",),
        r"^https://(?:www\.)?jobly\.fi/(?:en/)?(?:tyopaikka|job)/([\w-]+)", "path",
    ),
    _site(
        "alert_indeed", "Indeed job alerts", ("indeed.com", "indeed.fi"),
        r"^https://(?:[a-z]{2}\.|www\.)?indeed\.com/(?:rc/clk|viewjob|pagead/clk|applystart)[^#]*?[?&]jk=([0-9a-f]{8,24})",
        "https://fi.indeed.com/viewjob?jk={id}",
    ),
    _site(
        "alert_oikotie", "Oikotie job alerts", ("oikotie.fi",),
        r"^https://tyopaikat\.oikotie\.fi/tyopaikka/([\w-]+)", "path",
    ),
    _site(
        "alert_monster", "Monster job alerts", ("monster.fi", "monster.com"),
        r"^https://(?:www\.)?monster\.(?:fi|com)/(?:tyopaikka|job-openings|jobs?)/([\w-]+)", "path",
    ),
    _site(
        "alert_kuntarekry", "Kuntarekry job alerts", ("kuntarekry.fi",),
        r"^https://(?:www\.)?kuntarekry\.fi/(?:fi|en|sv)/tyopaikat/[^#?]*?(\d{5,})", "path",
    ),
    _site(
        "alert_tyomarkkinatori", "Job Market Finland alerts", ("tyomarkkinatori.fi",),
        r"^https://(?:www\.)?tyomarkkinatori\.fi/[^#?]*avoimet-tyopaikat/[^#?]*?([0-9a-f][0-9a-f-]{7,})", "path",
    ),
    # The Finnish State's job service: no feed or API; its own job alert emails are the route.
    # Format not yet checked against a real email (2026-11-11).
    _site(
        "alert_valtiolle", "Valtiolle job alerts", ("valtiolle.fi",),
        r"^https://(?:www\.|tuotanto\.)?valtiolle\.fi/(?:fi|en|se)/(?:tyopaikat|jobs|jobb|lediga-jobb)/[^#?]*?(\d{4,})", "path",
    ),
    # University career portals (e.g. UTU JobTeaser) sit behind the university login; their own
    # alert emails are the route. Format not yet checked against a real email (2026-11-14).
    _site(
        "alert_jobteaser", "JobTeaser job alerts", ("jobteaser.com",),
        r"^https://(?:[a-z0-9-]+\.)?jobteaser\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?(?:job-offers|sp_job_offers)/(\d{4,})", "path",
    ),
    # Sites whose pages refuse automated access: their own alert emails are the permitted route.
    _site(
        "alert_europeremotely", "Europe Remotely job alerts", ("europeremotely.com",),
        r"^https://(?:www\.)?europeremotely\.com/(?:jobs?|remote-jobs?)/([\w-]+)", "path",
    ),
    _site(
        "alert_ziprecruiter", "ZipRecruiter job alerts", ("ziprecruiter.com", "ziprecruiter.co.uk", "ziprecruiter.ie"),
        r"^https://(?:www\.)?ziprecruiter\.(?:com|co\.uk|ie)/[^#]*?[?&](?:jid|lvk)=([\w-]{6,})", None,
    ),
)
SITES_BY_KEY = {s.key: s for s in SITES}


@dataclass(frozen=True)
class AlertJob:
    title: str
    company: str
    location: str | None
    external_id: str
    link: str  # address shown to the user as the original posting
    canonical_url: str | None  # set only when the clean posting address is known
    posted_on: date | None  # from the card's stated age ("3d"); None when not stated
    age_text: str | None


@dataclass
class ParsedAlert:
    message_key: str
    site: AlertSite | None
    result: str  # parsed, no_jobs, unknown_sender, unverified_sender, too_large
    received_at: datetime | None = None
    jobs: list[AlertJob] = field(default_factory=list)
    unreadable_cards: int = 0


# ---------- Message level ----------


def message_key(raw: bytes) -> str:
    """Message-ID when present (stable across mailboxes), otherwise a hash of the email."""
    match = re.search(rb"^Message-ID:\s*(<[^>\r\n]{1,250}>)", raw[:65536], re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).decode("ascii", "replace")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _domain_matches(domain: str, allowed: tuple[str, ...]) -> bool:
    domain = domain.lower().rstrip(".")
    return any(domain == d or domain.endswith("." + d) for d in allowed)


def site_for_sender(address: str) -> AlertSite | None:
    domain = address.rpartition("@")[2]
    return next((s for s in SITES if domain and _domain_matches(domain, s.sender_domains)), None)


def _dkim_passed(msg: EmailMessage, site: AlertSite) -> bool:
    """The receiving server's own verdict (the topmost Authentication-Results header)."""
    headers = msg.get_all("Authentication-Results") or []
    if not headers:
        return False
    verdict = str(headers[0]).lower()
    for match in re.finditer(r"dkim=pass[^;]*?header\.(?:d|i)=@?([a-z0-9.-]+)", verdict):
        if _domain_matches(match.group(1), site.sender_domains):
            return True
    return False


def _received_at(msg: EmailMessage) -> datetime | None:
    try:
        value = parsedate_to_datetime(str(msg["Date"])) if msg["Date"] else None
    except (TypeError, ValueError):
        return None
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _body(msg: EmailMessage, subtype: str) -> str | None:
    part = msg.get_body(preferencelist=(subtype,))
    if part is None:
        return None
    try:
        return part.get_content()
    except (LookupError, ValueError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", "replace")


def parse_alert_email(raw: bytes) -> ParsedAlert:
    key = message_key(raw)
    if len(raw) > MAX_EMAIL_BYTES:
        return ParsedAlert(key, None, "too_large")
    msg = message_from_bytes(raw, policy=policy.default)
    site = site_for_sender(parseaddr(str(msg["From"] or ""))[1])
    if site is None:
        return ParsedAlert(key, None, "unknown_sender")
    received = _received_at(msg)
    if not _dkim_passed(msg, site):
        return ParsedAlert(key, site, "unverified_sender", received)

    cards: list[list[str]] = []
    links: list[str] = []
    text = _body(msg, "plain")
    if site.key == "alert_linkedin" and text:
        for link, segments in _linkedin_text_cards(text):
            links.append(link)
            cards.append(segments)
    if not cards:
        html = _body(msg, "html")
        if html:
            for link, segments in _html_cards(html, site):
                links.append(link)
                cards.append(segments)

    parsed = ParsedAlert(key, site, "parsed", received)
    seen: set[str] = set()
    for link, segments in zip(links, cards, strict=True):
        job = _card_to_job(site, link, segments, received)
        if job is None:
            parsed.unreadable_cards += 1
            continue
        if job.external_id in seen:
            continue
        seen.add(job.external_id)
        parsed.jobs.append(job)
        if len(parsed.jobs) >= MAX_JOBS_PER_EMAIL:
            break
    if not parsed.jobs:
        parsed.result = "no_jobs"
    return parsed


# ---------- Cards ----------

_VIEW_JOB = re.compile(r"^\s*View job:\s*(https://\S+)\s*$", re.IGNORECASE)
_SEPARATOR = re.compile(r"^\s*-{10,}\s*$")


def _linkedin_text_cards(text: str) -> list[tuple[str, list[str]]]:
    """LinkedIn's plain-text part: blocks of title / company / location, then "View job: <link>"."""
    cards = []
    block: list[str] = []
    for line in text.splitlines():
        if _SEPARATOR.match(line):
            block = []
            continue
        match = _VIEW_JOB.match(line)
        if not match:
            block.append(line.strip())
            continue
        paragraphs, current = [], []
        for item in block:
            if item:
                current.append(item)
            elif current:
                paragraphs.append(current)
                current = []
        if current:
            paragraphs.append(current)
        # The card is the last paragraph with three lines (title, company, location); an
        # alert's first block also starts with a heading line, which this drops.
        card = next((p[-3:] for p in reversed(paragraphs) if len(p) >= 3), None)
        if card is None:
            card = next((p[-2:] for p in reversed(paragraphs) if len(p) == 2), [])
        cards.append((match.group(1), card))
        block = []
    return cards


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, list[str]]] = []
        self._current: tuple[str, list[str]] | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script"):
            self._skip += 1
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            self._current = (unescape(href.strip()), [])

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script") and self._skip:
            self._skip -= 1
        elif tag == "a" and self._current is not None:
            self.anchors.append(self._current)
            self._current = None

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if self._current is not None and not self._skip and text:
            self._current[1].append(text)


def _html_cards(html: str, site: AlertSite) -> list[tuple[str, list[str]]]:
    """Link texts grouped by posting: one card may be spread over several links."""
    collector = _AnchorCollector()
    try:
        collector.feed(html)
        collector.close()
    except Exception:  # noqa: BLE001 - malformed markup just yields fewer cards
        pass
    grouped: dict[str, tuple[str, list[str]]] = {}
    for href, segments in collector.anchors:
        match = site.link.match(href)
        if not match:
            continue
        link, collected = grouped.setdefault(match.group(1), (href, []))
        collected.extend(s for s in segments if s not in collected)
    return list(grouped.values())


_AGE = re.compile(r"^(\d{1,3})\s*([hd])(\+?)$", re.IGNORECASE)
_NOISE = re.compile(
    r"^(?:\d(?:[.,]\d)?\s*★|★+|easy apply|helppo haku|apply now|hae nyt|new|uusi|promoted|"
    r"view job|this company is actively hiring|actively hiring|\d+\s+(?:school\s+)?alumn?(?:i|us)?|"
    r"\d+\s+connections?|be an early applicant|.*\bapplicants?\b.*)$",
    re.IGNORECASE,
)


def _clean(value: str) -> str:
    return " ".join(value.split())[:FIELD_MAX]


def _card_to_job(site: AlertSite, link: str, segments: list[str], received: datetime | None) -> AlertJob | None:
    match = site.link.match(link)
    if not match:
        return None
    posting_id = match.group(1)
    age_text = None
    values: list[str] = []
    for segment in segments:
        segment = _clean(segment)
        if _AGE.match(segment):
            age_text = segment
        elif segment and not _NOISE.match(segment):
            values.append(segment)
    named = dict(zip(site.order, values, strict=False))
    title, company = named.get("title"), named.get("company")
    if not title or not company:
        return None
    return AlertJob(
        title=title,
        company=company,
        location=named.get("location"),
        external_id=posting_id[:200],
        link=_display_link(site, link, posting_id),
        canonical_url=_canonical(site, link, posting_id),
        posted_on=_posted_on(age_text, received),
        age_text=age_text,
    )


def _canonical(site: AlertSite, link: str, posting_id: str) -> str | None:
    if site.canonical == "path":
        parts = urlsplit(link)
        return urlunsplit(("https", parts.netloc.lower(), parts.path, "", ""))
    if site.canonical:
        return site.canonical.format(id=posting_id)
    return None


def _display_link(site: AlertSite, link: str, posting_id: str) -> str:
    return _canonical(site, link, posting_id) or link[:2000]


def _posted_on(age_text: str | None, received: datetime | None) -> date | None:
    """"3d" in an email received on 10 Nov means posted 7 Nov. "30d+" is not a date."""
    if not age_text or received is None:
        return None
    match = _AGE.match(age_text)
    if not match or match.group(3):
        return None
    amount, unit = int(match.group(1)), match.group(2).lower()
    delta = timedelta(days=amount) if unit == "d" else timedelta(hours=amount)
    return (received - delta).date()
