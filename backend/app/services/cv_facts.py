"""Suggest profile facts from the extracted text of a CV.

Rule-based and local: no language model. The result is only a list of *suggestions*. Nothing
is saved until the user picks suggestions, and every saved fact starts ``unverified`` with the
CV as its evidence (verified facts are the source of truth; never invent claims).

The parser recognises common CV section headings (English, plus a few Finnish ones), contact
details, date ranges such as "Oct 2024 – Jun 2025", "2019 – 2022", "October 2024 to June
2025" or "Aug 2025 – exp. 2027", comma or dot separated skill lists and spoken languages.
Anything it cannot place is left out rather than guessed. References to other people
(recommendations, referees) are never suggested: they are other people's personal data.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date

from app.persistence.models import FactCategory

PARSER_VERSION = "cv-facts-1"
MAX_SUGGESTIONS = 200
MAX_VALUE_CHARS = 4000

SECTIONS: dict[str, FactCategory | None] = {
    # heading (lower case, "&" written as "and") -> category; None = skip the section
    "profile": FactCategory.SUMMARY,
    "summary": FactCategory.SUMMARY,
    "professional summary": FactCategory.SUMMARY,
    "about": FactCategory.SUMMARY,
    "about me": FactCategory.SUMMARY,
    "experience": FactCategory.WORK_EXPERIENCE,
    "work experience": FactCategory.WORK_EXPERIENCE,
    "professional experience": FactCategory.WORK_EXPERIENCE,
    "employment": FactCategory.WORK_EXPERIENCE,
    "employment history": FactCategory.WORK_EXPERIENCE,
    "työkokemus": FactCategory.WORK_EXPERIENCE,
    "education": FactCategory.EDUCATION,
    "education and training": FactCategory.EDUCATION,
    "koulutus": FactCategory.EDUCATION,
    "projects": FactCategory.PROJECT,
    "selected projects": FactCategory.PROJECT,
    "personal projects": FactCategory.PROJECT,
    "projektit": FactCategory.PROJECT,
    "skills": FactCategory.SKILL,
    "technical skills": FactCategory.SKILL,
    "digital skills": FactCategory.SKILL,
    "key skills": FactCategory.SKILL,
    "taidot": FactCategory.SKILL,
    "languages": FactCategory.LANGUAGE,
    "language skills": FactCategory.LANGUAGE,
    "kielitaito": FactCategory.LANGUAGE,
    "certifications": FactCategory.CERTIFICATION,
    "certificates": FactCategory.CERTIFICATION,
    "licenses and certifications": FactCategory.CERTIFICATION,
    "sertifikaatit": FactCategory.CERTIFICATION,
    "publication": FactCategory.PUBLICATION,
    "publications": FactCategory.PUBLICATION,
    "research and publication": FactCategory.PUBLICATION,
    "research and publications": FactCategory.PUBLICATION,
    "research": FactCategory.PUBLICATION,
    "achievements": FactCategory.ACHIEVEMENT,
    "awards": FactCategory.ACHIEVEMENT,
    "honours and awards": FactCategory.ACHIEVEMENT,
    "honors and awards": FactCategory.ACHIEVEMENT,
    "conferences and seminars": FactCategory.ACHIEVEMENT,
    "volunteering": FactCategory.WORK_EXPERIENCE,
    "volunteer experience": FactCategory.WORK_EXPERIENCE,
    "recommendations": None,
    "references": None,
    "referees": None,
    "suosittelijat": None,
    "hobbies": None,
    "interests": None,
}

# Labels that may start a line inside a skills section and move it to another category.
SKILL_SUBLABELS: dict[str, FactCategory | None] = {
    "languages": FactCategory.LANGUAGE,
    "language": FactCategory.LANGUAGE,
    "certificates": FactCategory.CERTIFICATION,
    "certifications": FactCategory.CERTIFICATION,
    "other": None,
}

LANGUAGE_NAMES = (
    "english", "finnish", "swedish", "german", "french", "spanish", "italian", "portuguese", "russian",
    "estonian", "norwegian", "danish", "dutch", "polish", "ukrainian", "arabic", "turkish", "persian",
    "farsi", "hindi", "urdu", "bengali", "bangla", "tamil", "nepali", "chinese", "mandarin", "cantonese",
    "japanese", "korean", "vietnamese", "thai", "indonesian", "somali", "kurdish", "greek", "hungarian",
    "czech", "romanian", "suomi", "englanti", "ruotsi", "saksa",
)

MONTHS = {
    **{name.lower(): i for i, name in enumerate(calendar.month_name) if name},
    **{name.lower(): i for i, name in enumerate(calendar.month_abbr) if name},
    "sept": 9,
}
_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_POINT = rf"(?:(?:{_MONTH}\s+)?(?:19|20)\d{{2}}|(?:0?[1-9]|1[0-2])[/.](?:19|20)\d{{2}})"
_OPEN_END = r"(?:present|current|now|ongoing|today|nykyään|exp\.?\s*(?:{m}\s+)?(?:19|20)\d{{2}}|expected\s+(?:{m}\s+)?(?:19|20)\d{{2}})".format(m=_MONTH)
_SEP = r"\s*(?:[-–—]|to|until|–)\s*"
# A range or a single point at the END of a line (optionally followed by "." or ")").
DATE_AT_END = re.compile(
    rf"(?P<start>{_POINT})(?:{_SEP}(?P<end>{_POINT}|{_OPEN_END}))?\s*[.)]?\s*$", re.IGNORECASE
)
YEAR_ONLY = re.compile(r"^(?:19|20)\d{2}$")

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w/])(?:\(\+\d{1,4}\)|\+\d)[\d\s()-]{6,18}\d")
URL = re.compile(r"(?:https?://)?(?:www\.)?((?:github\.com|linkedin\.com|gitlab\.com)/[A-Za-z0-9_./-]+|[a-z0-9-]+\.github\.io(?:/[A-Za-z0-9_./-]*)?)", re.IGNORECASE)
BULLET = re.compile(r"^\s*(?:[•●▪◦·*-]|•)\s*")


@dataclass
class Suggestion:
    category: FactCategory
    subject: str
    value_text: str
    valid_from: date | None = None
    valid_until: date | None = None
    excerpt: str = ""


@dataclass
class _Entry:
    header: list[str] = field(default_factory=list)
    body: list[str] = field(default_factory=list)
    start: date | None = None
    end: date | None = None


def _heading_key(line: str) -> str | None:
    text = line.strip().rstrip(":").strip()
    if not text or len(text) > 45 or any(ch.isdigit() for ch in text):
        return None
    key = re.sub(r"\s+", " ", text.replace("&", "and")).lower()
    return key if key in SECTIONS else None


def _parse_point(text: str, *, end: bool) -> date | None:
    text = text.strip().rstrip(".").lower()
    if re.match(r"^(present|current|now|ongoing|today|nykyään)$", text):
        return None
    text = re.sub(r"^(exp\.?|expected)\s*", "", text)
    match = re.match(r"^(?:([a-z]+)\.?\s+)?((?:19|20)\d{2})$", text)
    if match:
        month = MONTHS.get(match.group(1) or "", 0)
        year = int(match.group(2))
        if not month:
            return date(year, 12, 31) if end else date(year, 1, 1)
        return date(year, month, calendar.monthrange(year, month)[1]) if end else date(year, month, 1)
    match = re.match(r"^(\d{1,2})[/.]((?:19|20)\d{2})$", text)
    if match:
        month, year = int(match.group(1)), int(match.group(2))
        return date(year, month, calendar.monthrange(year, month)[1]) if end else date(year, month, 1)
    return None


def _dates(match: re.Match) -> tuple[date | None, date | None]:
    start = _parse_point(match.group("start"), end=False)
    end_text = match.group("end")
    if end_text is None:
        # A single point ("2026", "Dec 2023"): a project or publication date.
        return start, _parse_point(match.group("start"), end=True)
    lowered = end_text.lower()
    if lowered.startswith(("exp", "expected")):
        return start, None  # not finished: an expected end is not a fact yet
    end = _parse_point(end_text, end=True)
    if start and end and start > end:
        return None, None
    return start, end


def _headerish(line: str) -> bool:
    words = line.split()
    return 0 < len(words) <= 9 and not line.rstrip().endswith((".", ",", ";", ":")) and not BULLET.match(line)


def _clean(text: str) -> str:
    text = BULLET.sub("", text)
    return re.sub(r"\s+", " ", text).strip(" ·|,;-–")


def _join_body(lines: list[str]) -> str:
    """Join description lines into running text, keeping the punctuation at line ends.

    A metadata line ("Hackathon 2026 · Lead developer · github.com/…") becomes its own sentence
    so it does not run into the description that follows.
    """
    parts: list[str] = []
    for raw in lines:
        line = re.sub(r"\s+", " ", BULLET.sub("", raw)).strip()
        if not line:
            continue
        if " · " in line and not line.endswith((".", "!", "?", ",", ";", ":")):
            line = line.rstrip(" ·") + "."
        elif BULLET.match(raw) and parts and not parts[-1].endswith((".", "!", "?", ":", ";", ",")):
            parts[-1] += "."
        parts.append(line)
    return " ".join(parts)


def _split_sections(lines: list[str]) -> list[tuple[FactCategory | None, list[str]]]:
    sections: list[tuple[FactCategory | None, list[str]]] = []
    current: list[str] | None = None
    for line in lines:
        key = _heading_key(line)
        if key is not None:
            current = []
            sections.append((SECTIONS[key], current))
        elif current is not None:
            current.append(line)
    return sections


SINGLE_DATE_OK = {FactCategory.PROJECT, FactCategory.PUBLICATION, FactCategory.ACHIEVEMENT, FactCategory.CERTIFICATION}


def _entries(lines: list[str], single_date_ok: bool = True) -> list[_Entry]:
    """Split an experience-like section into entries anchored on date lines.

    In work and education sections only ranges ("2019 – 2022", "Aug 2025 – present") start an
    entry; a lone year there is usually a detail ("thesis published at … 2023").
    """
    entries: list[_Entry] = []
    current: _Entry | None = None
    pending: list[str] = []  # header-ish lines seen since the last body line
    any_dates = any(DATE_AT_END.search(line) for line in lines if line.strip())
    if not any_dates:
        return _paragraph_entries(lines)
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        match = DATE_AT_END.search(line)
        if match and match.group("end") is None and not single_date_ok:
            match = None
        if match and not _is_body_date(line, match):
            subject = _clean(line[: match.start()])
            header = []
            # A date-only line, or one with only place/contract words, takes the lines above it.
            if pending and (not subject or len(subject.split()) <= 6 or "·" not in line):
                header = pending[-2:]
                if current is not None:
                    current.body = [b for b in current.body if b not in header]
            entry = _Entry(header=[*header, subject] if subject else header)
            entry.start, entry.end = _dates(match)
            entries.append(entry)
            current = entry
            pending = []
            continue
        if _headerish(line):
            pending.append(line)
        else:
            pending = []
        if current is not None:
            current.body.append(line)
    return entries


def _is_body_date(line: str, match: re.Match) -> bool:
    # "… with Wilson confidence interval in 2023." is description text, not an entry header.
    before = line[: match.start()]
    return len(before.split()) > 14 and before.rstrip().endswith((",", " in", " since", " from"))


def _paragraph_entries(lines: list[str]) -> list[_Entry]:
    """Sections without dates: a short heading line starts an entry, paragraphs follow it."""
    entries: list[_Entry] = []
    current: _Entry | None = None
    previous_blank = True
    for raw in lines:
        line = raw.strip()
        if not line:
            previous_blank = True
            continue
        if _headerish(line) and (previous_blank or current is None) and len(line) <= 60:
            current = _Entry(header=[line])
            entries.append(current)
        elif current is not None:
            current.body.append(line)
        else:
            current = _Entry(header=[line[:80]], body=[line])
            entries.append(current)
        previous_blank = False
    return entries


def _entry_suggestions(category: FactCategory, lines: list[str]) -> list[Suggestion]:
    result = []
    for entry in _entries(lines, single_date_ok=category in SINGLE_DATE_OK):
        header = " · ".join(_clean(h) for h in entry.header if _clean(h))
        if not header:
            continue
        body = _join_body(entry.body)
        value = f"{header}. {body}".strip() if body else header
        excerpt = "\n".join([*entry.header, *entry.body])
        result.append(
            Suggestion(category, header[:300], value[:MAX_VALUE_CHARS], entry.start, entry.end, excerpt[:2000])
        )
    return result


def _split_outside_parens(text: str, separators: str) -> list[str]:
    depth, buffer, parts = 0, "", []
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if depth <= 0 and ch in separators:
            parts.append(buffer)
            buffer = ""
        else:
            buffer += ch
    parts.append(buffer)
    return parts


def _items(text: str) -> list[str]:
    return [_clean(p) for p in _split_outside_parens(text, ",;·•|\n") if _clean(p)]


def _join_wrapped(lines: list[str]) -> str:
    """Join list lines; a line starting in lower case continues the previous one."""
    text = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if text and line[0].islower() and not text.endswith((",", ";", "·")):
            text += " " + line
        else:
            text += ("\n" if text else "") + line
    return text


def _language_suggestions(text: str) -> list[Suggestion]:
    result = []
    # "Bengali (native) · English (C1–C2)": split on separators outside parentheses.
    parts = []
    names = "|".join(LANGUAGE_NAMES)
    for part in _split_outside_parens(text, ",;·•|\n"):
        # "Bengali (native) English (C1 to C2)": several languages without a separator.
        starts = [m.start() for m in re.finditer(rf"\b(?:{names})\b(?![^()]*\))", part, re.IGNORECASE)]
        if len(starts) > 1:
            parts.extend(part[a:b] for a, b in zip(starts, [*starts[1:], len(part)], strict=True))
        else:
            parts.append(part)
    for part in parts:
        item = _clean(part)
        lowered = item.lower()
        name = next((n for n in LANGUAGE_NAMES if re.search(rf"\b{n}\b", lowered)), None)
        if not name or len(item) > 200:
            continue
        subject = re.search(rf"\b{name}\b", item, re.IGNORECASE).group(0).capitalize()
        result.append(Suggestion(FactCategory.LANGUAGE, subject, item, excerpt=item))
    return result


def _skill_suggestions(lines: list[str]) -> list[Suggestion]:
    result: list[Suggestion] = []
    groups: list[tuple[FactCategory | None, str]] = []
    for line in _join_wrapped(lines).split("\n"):
        if not line:
            continue
        first = line.split()[0].rstrip(":").lower()
        if first in SKILL_SUBLABELS:
            groups.append((SKILL_SUBLABELS[first], line[len(line.split()[0]):]))
        elif groups and groups[-1][0] != FactCategory.SKILL and not _starts_new_skill_line(line):
            # Wrapped continuation of a languages/certificates line.
            groups[-1] = (groups[-1][0], groups[-1][1] + " " + line)
        else:
            groups.append((FactCategory.SKILL, line))
    for category, text in groups:
        if category == FactCategory.LANGUAGE:
            result.extend(_language_suggestions(text))
        elif category == FactCategory.CERTIFICATION:
            for item in re.split(r"\s*·\s*", text):
                if _clean(item):
                    result.append(Suggestion(FactCategory.CERTIFICATION, _clean(item)[:300], _clean(item), excerpt=item.strip()))
        elif category == FactCategory.SKILL:
            for item in _items(text):
                words = item.split()
                if 0 < len(words) <= 5 and len(item) <= 60 and not item.endswith("."):
                    result.append(Suggestion(FactCategory.SKILL, item, item, excerpt=text.strip()[:2000]))
    return result


def _starts_new_skill_line(line: str) -> bool:
    return line.split()[0].rstrip(":").lower() in SKILL_SUBLABELS


def _contact_suggestions(text: str) -> list[Suggestion]:
    # Only the top of the CV, before its first section: addresses further down belong to
    # employers or referees, not to the user.
    lines = text.split("\n")
    first_heading = next((i for i, line in enumerate(lines) if _heading_key(line) is not None), None)
    head = "\n".join(lines[:first_heading]) if first_heading else text
    head = head[:3000]
    result: list[Suggestion] = []
    seen: set[str] = set()

    def add(subject: str, value: str) -> None:
        if value.lower() not in seen:
            seen.add(value.lower())
            result.append(Suggestion(FactCategory.CONTACT, subject, value, excerpt=value))

    for email in EMAIL.findall(head):
        add("Email", email)
    for phone in PHONE.findall(head):
        add("Phone", re.sub(r"\s+", " ", phone).strip())
    for url in URL.findall(head):
        url = url.rstrip("./")
        lowered = url.lower()
        label = "GitHub" if lowered.startswith("github.com") else "LinkedIn" if "linkedin" in lowered else (
            "GitLab" if "gitlab" in lowered else "Website")
        if label == "GitHub" and url.count("/") > 1:
            continue  # a repository link belongs to a project, not to contact details
        add(label, url)
    return result


def suggest_facts(text: str) -> list[Suggestion]:
    """Return fact suggestions for one CV's extracted text, in reading order."""
    lines = text.replace("\r\n", "\n").split("\n")
    suggestions = _contact_suggestions(text)
    for category, section in _split_sections(lines):
        if category is None:
            continue
        if category == FactCategory.SUMMARY:
            body = _join_body(section)
            if body:
                suggestions.append(Suggestion(category, "Professional summary", body[:MAX_VALUE_CHARS], excerpt=body[:2000]))
        elif category == FactCategory.SKILL:
            suggestions.extend(_skill_suggestions(section))
        elif category == FactCategory.LANGUAGE:
            suggestions.extend(_language_suggestions("\n".join(section)))
        elif category == FactCategory.CERTIFICATION and not any(DATE_AT_END.search(s) for s in section):
            for line in section:
                if _clean(line):
                    suggestions.append(Suggestion(category, _clean(line)[:300], _clean(line), excerpt=line.strip()))
        else:
            suggestions.extend(_entry_suggestions(category, section))
    return _dedupe(suggestions)[:MAX_SUGGESTIONS]


def fact_key(category: str, subject: str, value_text: str) -> tuple[str, str, str]:
    norm = lambda s: re.sub(r"[^\w]+", " ", s.lower()).strip()  # noqa: E731
    return category, norm(subject), norm(value_text)


def _dedupe(items: list[Suggestion]) -> list[Suggestion]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for item in items:
        key = fact_key(item.category.value, item.subject, item.value_text)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
