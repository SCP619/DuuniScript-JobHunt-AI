"""Extract a schema.org ``JobPosting`` from a page's JSON-LD structured data.

This parser only reads data the page publishes for machines. It never guesses:
fields that are absent or ambiguous stay ``None``. All text is untrusted and is
returned as plain text with markup removed.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Any

from app.adapters.job_sources.language import detect_language, primary_language
from app.persistence.models import EmploymentType, WorkMode

PARSER_VERSION = "jsonld-3"
MAX_DESCRIPTION_CHARS = 100_000

EMPLOYMENT_TYPES = {
    "FULL_TIME": EmploymentType.FULL_TIME,
    "PART_TIME": EmploymentType.PART_TIME,
    "CONTRACTOR": EmploymentType.CONTRACT,
    "CONTRACT": EmploymentType.CONTRACT,
    "TEMPORARY": EmploymentType.TEMPORARY,
    "INTERN": EmploymentType.INTERNSHIP,
    "INTERNSHIP": EmploymentType.INTERNSHIP,
    "VOLUNTEER": EmploymentType.VOLUNTEER,
    "PER_DIEM": EmploymentType.PER_DIEM,
    "OTHER": EmploymentType.OTHER,
}

# Unambiguous Finnish and Swedish words. Contract-duration words (vakinainen, määräaikainen,
# tillsvidare, visstid) describe permanence, not working time, and are deliberately not mapped.
LOCAL_EMPLOYMENT_WORDS = {
    "kokoaikatyö": EmploymentType.FULL_TIME,
    "kokoaikainen": EmploymentType.FULL_TIME,
    "heltid": EmploymentType.FULL_TIME,
    "osa-aikatyö": EmploymentType.PART_TIME,
    "osa-aikainen": EmploymentType.PART_TIME,
    "deltid": EmploymentType.PART_TIME,
    "harjoittelu": EmploymentType.INTERNSHIP,
    "harjoittelija": EmploymentType.INTERNSHIP,
    "praktik": EmploymentType.INTERNSHIP,
}


@dataclass
class ParsedJob:
    title: str
    company: str
    description: str | None = None
    location: str | None = None
    employment_type: EmploymentType | None = None
    work_mode: WorkMode | None = None
    salary_text: str | None = None
    language: str | None = None
    external_id: str | None = None
    url: str | None = None
    published_on: date | None = None
    deadline_on: date | None = None
    deadline_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class NoJobPosting(Exception):
    """The page has no usable JobPosting structured data."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ---------- HTML helpers ----------


class _ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.blocks: list[str] = []
        self._capturing = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            kind = (dict(attrs).get("type") or "").split(";")[0].strip().lower()
            if kind == "application/ld+json":
                self._capturing = True
                self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capturing:
            self.blocks.append("".join(self._buffer))
            self._capturing = False

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._buffer.append(data)


BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "table"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in BLOCK_TAGS and tag != "li":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    if "&lt;" in value or "&gt;" in value:
        value = html.unescape(value)
    extractor = _TextExtractor()
    extractor.feed(value)
    extractor.close()
    text = "".join(extractor.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def _short(value: Any, limit: int = 300) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = str(value)
    text = html_to_text(value) if isinstance(value, str) else None
    if not text:
        return None
    return " ".join(text.split())[:limit]


# ---------- JSON-LD discovery ----------


def find_job_posting(page_html: str) -> dict[str, Any]:
    collector = _ScriptCollector()
    collector.feed(page_html)
    collector.close()
    if not collector.blocks:
        raise NoJobPosting("no_structured_data")
    for block in collector.blocks:
        try:
            data = json.loads(block, strict=False)
        except json.JSONDecodeError:
            continue
        found = _search(data)
        if found is not None:
            return found
    raise NoJobPosting("no_job_posting")


def _is_job_posting(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return any(isinstance(k, str) and k.split("/")[-1] == "JobPosting" for k in kinds)


def _search(node: Any, depth: int = 0) -> dict[str, Any] | None:
    if depth > 6:
        return None
    if isinstance(node, list):
        for item in node:
            found = _search(item, depth + 1)
            if found is not None:
                return found
    elif isinstance(node, dict):
        if _is_job_posting(node):
            return node
        if "@graph" in node:
            return _search(node["@graph"], depth + 1)
    return None


# ---------- Field mapping ----------


DATE_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})")


def _date_part(value: Any) -> date | None:
    """The calendar date exactly as published, without timezone conversion."""
    if not isinstance(value, str):
        return None
    match = DATE_RE.match(value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _aware_datetime(value: Any) -> datetime | None:
    """A full timestamp only when the source states both time and timezone."""
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _organization(value: Any) -> str | None:
    if isinstance(value, dict):
        return _short(value.get("name"))
    if isinstance(value, list) and value:
        return _organization(value[0])
    return _short(value)


def _place(value: Any) -> str | None:
    if isinstance(value, list):
        places = list(dict.fromkeys(p for p in (_place(v) for v in value) if p))
        # Drop places fully covered by a more specific one (e.g. "FI" next to "Turku, FI").
        part_sets = {p: set(p.split(", ")) for p in places}
        kept = [p for p in places if not any(q != p and part_sets[p] < part_sets[q] for q in places)]
        return "; ".join(kept)[:300] or None
    if not isinstance(value, dict):
        return _short(value)
    address = value.get("address", value)
    if isinstance(address, str):
        return _short(address)
    if not isinstance(address, dict):
        return _short(value.get("name"))
    country = address.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    parts = [address.get("addressLocality"), address.get("addressRegion"), country]
    cleaned = [p for p in (_short(x) for x in parts) if p]
    return ", ".join(dict.fromkeys(cleaned)) or _short(value.get("name"))


def _employment_type(value: Any) -> EmploymentType | None:
    """Map schema.org codes, or unambiguous Finnish/Swedish words, to an employment type.

    Finnish boards (e.g. Kuntarekry, Valtiolle) publish free text such as
    "Kokoaikatyö, 3-vuorotyö, Vakinainen, Työsuhde". Only full-time, part-time and
    internship words are mapped; anything else stays unknown rather than guessed.
    """
    raw = value if isinstance(value, list) else [value]
    items = [part.strip() for item in raw if isinstance(item, str) for part in item.split(",")]
    for item in items:
        mapped = EMPLOYMENT_TYPES.get(item.upper().replace("-", "_").replace(" ", "_"))
        if mapped:
            return mapped
    found = {LOCAL_EMPLOYMENT_WORDS[w] for w in (i.lower() for i in items) if w in LOCAL_EMPLOYMENT_WORDS}
    return found.pop() if len(found) == 1 else None


def _work_mode(posting: dict[str, Any]) -> WorkMode | None:
    kind = posting.get("jobLocationType")
    kinds = kind if isinstance(kind, list) else [kind]
    if any(isinstance(k, str) and k.strip().upper() == "TELECOMMUTE" for k in kinds):
        # Remote is only claimed when the page explicitly says so; on-site is never assumed.
        return WorkMode.REMOTE
    return None


def _amount(value: Any) -> str | None:
    """A salary figure only if it is actually a number (ignores "" and placeholders)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return f"{value:g}"
    text = str(value).strip()
    return text if re.fullmatch(r"\d[\d\s.,]*", text) else None


def _salary(value: Any) -> str | None:
    if not isinstance(value, dict):
        return _short(value)
    currency = _short(value.get("currency"), 10) or ""
    amount = value.get("value")
    if isinstance(amount, dict):
        unit = _short(amount.get("unitText"), 20) or ""
        low, high, exact = (_amount(amount.get(k)) for k in ("minValue", "maxValue", "value"))
        if low and high:
            figure = low if low == high else f"{low}–{high}"
        else:
            figure = exact or low or high
        if not figure:
            return None  # no real amount published
        text = f"{figure} {currency}".strip()
        return (f"{text} / {unit.lower()}" if unit else text)[:300]
    number = _amount(amount)
    if number:
        return f"{number} {currency}".strip()[:300]
    # Free-text salary (common on Finnish boards): keep the publisher's wording unchanged.
    return _short(amount) if isinstance(amount, str) else None


def _identifier(value: Any) -> str | None:
    if isinstance(value, dict):
        return _short(value.get("value") or value.get("@id") or value.get("name"))
    if isinstance(value, list) and value:
        return _identifier(value[0])
    return _short(value)


def _language(value: Any) -> str | None:
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        value = value.get("alternateName") or value.get("name")
    return primary_language(value) if isinstance(value, str) else None


def parse_job_posting(page_html: str) -> ParsedJob:
    posting = find_job_posting(page_html)
    title = _short(posting.get("title"))
    company = _organization(posting.get("hiringOrganization"))
    if not title or not company:
        raise NoJobPosting("missing_title_or_company")
    description = html_to_text(posting.get("description"))
    url = posting.get("url") if isinstance(posting.get("url"), str) else None
    valid_through = posting.get("validThrough")
    return ParsedJob(
        title=title,
        company=company,
        description=description[:MAX_DESCRIPTION_CHARS] if description else None,
        location=_place(posting.get("jobLocation")),
        employment_type=_employment_type(posting.get("employmentType")),
        work_mode=_work_mode(posting),
        salary_text=_salary(posting.get("baseSalary")),
        # Stated by the page if it says so, otherwise detected from the advertisement text itself.
        language=_language(posting.get("inLanguage")) or detect_language(f"{title}\n{description or ''}"),
        external_id=_identifier(posting.get("identifier")),
        url=url,
        published_on=_date_part(posting.get("datePosted")),
        deadline_on=_date_part(valid_through),
        deadline_at=_aware_datetime(valid_through),
        raw=posting,
    )
