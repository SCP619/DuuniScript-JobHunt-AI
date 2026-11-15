"""Is a newly seen job one that is already in the list? (duplicate detection, stage 2)

Stage 1 (exact) lives in job_service: the same posting address or the same site posting ID.
This stage compares what the postings say, so the same job seen on two sites becomes one job
and is never applied to twice:

- company and job title must match after normalisation (case, punctuation, legal forms such
  as Oy/Ltd/GmbH, country tags such as "(FI)", gender markers such as "(m/f/d)");
- listing dates more than ``MAX_DATE_GAP_DAYS`` apart, clearly different locations, or clearly
  different descriptions make it only a *possible* duplicate, because companies reuse titles;
- a description is compared only when both jobs have one. Alert emails carry none, and the
  same job may be advertised in Finnish on one site and in English on another, so a low
  similarity alone never proves two jobs are different.

Outcomes: ``same`` (merge into the existing job), ``possible`` (keep both, flag the new one
for the user to decide) or ``different``. A wrong merge would hide a job, so anything short of
a clear match is ``possible``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import Job

Verdict = Literal["same", "possible", "different"]

MAX_DATE_GAP_DAYS = 45
MIN_DESCRIPTION_CHARS = 200
SAME_DESCRIPTION = 0.6
NEAR_TITLE = 0.85

LEGAL_FORMS = {
    "oy", "oyj", "ab", "abp", "ky", "ay", "ry", "tmi", "ltd", "limited", "inc", "incorporated", "llc",
    "plc", "gmbh", "ag", "as", "asa", "aps", "sa", "bv", "nv", "corp", "corporation", "co", "company",
}
COUNTRY_WORDS = {"finland", "suomi", "fi", "finland's"}
GENDER_MARKER = re.compile(r"\((?:[mfwdxn]\s*/\s*){1,3}[mfwdxn]\)|\b(?:[mfwdxn]/){1,3}[mfwdxn]\b", re.IGNORECASE)
PARENTHESES = re.compile(r"\([^)]*\)")
NON_WORD = re.compile(r"[^\w]+")


def _fold(text: str | None) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return NON_WORD.sub(" ", text).replace("_", " ").strip()


def company_key(company: str | None) -> str:
    words = _fold(PARENTHESES.sub(" ", company or "")).split()
    kept = [w for w in words if w not in LEGAL_FORMS and w not in COUNTRY_WORDS]
    return " ".join(kept or words)


def title_key(title: str | None) -> str:
    return " ".join(_fold(GENDER_MARKER.sub(" ", title or "")).split())


def _words(text: str | None) -> set[str]:
    return {w for w in _fold(text).split() if len(w) > 1}


def _shingles(text: str, size: int = 3) -> set[tuple[str, ...]]:
    words = _fold(text).split()
    return {tuple(words[i : i + size]) for i in range(max(len(words) - size + 1, 1))}


def description_similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


@dataclass(frozen=True)
class Posting:
    """The fields that identify a posting. ``listed_on`` is the stated date or the first-seen date."""

    company: str
    title: str
    location: str | None = None
    description: str | None = None
    listed_on: date | None = None


def compare(new: Posting, old: Posting) -> Verdict:
    if not company_key(new.company) or company_key(new.company) != company_key(old.company):
        return "different"
    new_title, old_title = title_key(new.title), title_key(old.title)
    if new_title == old_title or sorted(new_title.split()) == sorted(old_title.split()):
        strong = True
    elif SequenceMatcher(None, new_title, old_title).ratio() >= NEAR_TITLE or (
        min(len(new_title), len(old_title)) >= 8 and (new_title in old_title or old_title in new_title)
    ):
        strong = False
    else:
        return "different"

    if new.listed_on and old.listed_on and abs((new.listed_on - old.listed_on).days) > MAX_DATE_GAP_DAYS:
        strong = False  # same title much later: possibly a new round of hiring
    if new.location and old.location and not (_words(new.location) & _words(old.location)):
        strong = False  # e.g. the same role advertised for two cities
    if (
        new.description
        and old.description
        and min(len(new.description), len(old.description)) >= MIN_DESCRIPTION_CHARS
        and description_similarity(new.description, old.description) < SAME_DESCRIPTION
    ):
        strong = False  # different text: another vacancy, or a translation
    return "same" if strong else "possible"


def same_place(a: str | None, b: str | None) -> bool:
    """Exactly the same stated location (after case and punctuation), or neither states one."""
    return _fold(a) == _fold(b)


def listed_on(job: Job) -> date | None:
    return job.published_on or (job.first_seen_at.date() if job.first_seen_at else None)


def find_match(session: Session, new: Posting, exclude_id: str | None = None) -> tuple[Verdict, Job | None]:
    """The best existing match: a ``same`` job if there is one, else a ``possible`` one."""
    key = company_key(new.company)
    if not key:
        return "different", None
    # Narrow by the first word of the company in SQL; the full comparison is done in Python.
    # (SQLite folds case for ASCII only, so other words are compared in Python alone.)
    first = key.split()[0]
    query = select(Job).order_by(Job.first_seen_at)
    if first.isascii():
        query = query.where(Job.company.ilike(f"%{first}%"))
    candidates = session.scalars(query)
    possible: Job | None = None
    for job in candidates:
        if job.id == exclude_id:
            continue
        verdict = compare(
            new,
            Posting(job.company, job.title, job.location, job.description, listed_on(job)),
        )
        if verdict == "same":
            return "same", job
        if verdict == "possible" and possible is None:
            possible = job
    return ("possible", possible) if possible else ("different", None)
