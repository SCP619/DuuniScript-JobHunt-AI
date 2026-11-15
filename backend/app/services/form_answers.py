"""Answers to the questions application forms always ask, ready to copy.

Every answer comes from the user's profile, *verified* facts, the job posting (only to quote it)
or an answer the user wrote and saved. Nothing is invented: when no source exists the answer is
left empty with ``needs_input`` and a hint. Saved answers are reused for every application;
job-specific ones ("why us") are saved per application.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.persistence.models import Application, Job, SavedAnswer, utcnow
from app.services import drafting

GENERAL_KEYS = ("availability", "salary", "notice_period", "references", "relocation")
PER_APPLICATION_KEYS = ("why_us",)
KEY = re.compile(r"^(availability|salary|notice_period|references|relocation|why_us:[0-9a-f-]{36})$")
PERMIT = re.compile(r"work permit|residence permit|right to work|työlupa|oleskelulupa|citizen|kansalai", re.IGNORECASE)


@dataclass
class Answer:
    key: str
    question: str
    answer: str
    source: str  # "facts", "profile", "saved", "job", "none"
    needs_input: bool = False
    hint: str | None = None
    fact_ids: list[str] = field(default_factory=list)


def _saved(session: Session) -> dict[str, str]:
    return {row.key: row.answer for row in session.scalars(select(SavedAnswer))}


def save(session: Session, key: str, answer: str | None) -> None:
    if not KEY.match(key):
        raise AppError(422, "unknown_question", "This question cannot be saved.")
    row = session.get(SavedAnswer, key)
    if not answer or not answer.strip():
        if row is not None:
            session.delete(row)
    elif row is None:
        session.add(SavedAnswer(key=key, answer=answer.strip()[:5000]))
    else:
        row.answer, row.updated_at = answer.strip()[:5000], utcnow()
    session.commit()


def _months(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + end.month - start.month + 1)


def experience_months(facts: list[drafting.FactView], today: date) -> int:
    """Months covered by verified work periods (overlaps counted once). Open-ended periods are
    skipped: an unknown end is not assumed to be today."""
    spans = sorted((f.valid_from, f.valid_until) for f in facts
                   if f.category == "work_experience" and f.valid_from and f.valid_until)
    total, current_start, current_end = 0, None, None
    for start, end in spans:
        if current_end is None or start > current_end:
            if current_end is not None:
                total += _months(current_start, current_end)
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None:
        total += _months(current_start, current_end)
    return total


def answers(session: Session, application: Application, person: drafting.PersonView,
            facts: list[drafting.FactView], job: Job, today: date | None = None) -> list[Answer]:
    today = today or date.today()
    saved = _saved(session)
    out: list[Answer] = []

    def saved_answer(key: str, question: str, hint: str, store_key: str | None = None) -> None:
        text = saved.get(store_key or key)
        if text:
            out.append(Answer(key, question, text, "saved"))
        else:
            out.append(Answer(key, question, "", "none", True, hint))

    # Right to work
    permit = [f for f in facts if PERMIT.search(f"{f.subject} {f.value_text}")]
    sources = permit or ([] if not person.professional_summary or not PERMIT.search(person.professional_summary) else None)
    if permit:
        sentence = next((s for f in permit for s in re.split(r"(?<=[.!?·])\s+", f.value_text) if PERMIT.search(s)), permit[0].value_text)
        out.append(Answer("work_permit", "Do you have the right to work in Finland?", sentence.strip(" ·"), "facts",
                          fact_ids=[f.id for f in permit]))
    elif sources is None:
        sentence = next(s for s in re.split(r"(?<=[.!?·])\s+", person.professional_summary) if PERMIT.search(s))
        out.append(Answer("work_permit", "Do you have the right to work in Finland?", sentence.strip(" ·"), "profile"))
    else:
        out.append(Answer("work_permit", "Do you have the right to work in Finland?", "", "none", True,
                          "Add a verified fact about your residence or work permit (e.g. from your CV header)."))

    out.append(Answer("location", "Where are you based?", person.location or "", "profile" if person.location else "none",
                      not person.location, None if person.location else "Add your location in the profile."))
    saved_answer("availability", "When could you start?", "Write once, e.g. “From January 2027, part-time during studies.”")
    hint = "Write your expectation once; it is reused."
    if job.salary_text:
        hint += f" The posting states: {job.salary_text}"
    saved_answer("salary", "What is your salary expectation?", hint)
    saved_answer("notice_period", "What is your notice period?", "Write once, e.g. “Available immediately.”")

    languages = [f for f in facts if f.category == "language"]
    out.append(Answer("languages", "Language skills", "; ".join(f.value_text for f in languages),
                      "facts" if languages else "none", not languages,
                      None if languages else "Add verified language facts.", [f.id for f in languages]))

    months = experience_months(facts, today)
    roles = [f for f in facts if f.category == "work_experience" and f.valid_from and f.valid_until]
    if months:
        years = months / 12
        amount = f"about {years:.1f} years".replace(".0 years", " years") if years >= 1 else f"{months} months"
        out.append(Answer("experience", "How much work experience do you have?",
                          f"{amount[0].upper()}{amount[1:]} in {len(roles)} role{'s' if len(roles) != 1 else ''}: "
                          + "; ".join(f"{r.subject} ({drafting.format_period(r.valid_from, r.valid_until)})" for r in roles),
                          "facts", fact_ids=[r.id for r in roles]))
    else:
        out.append(Answer("experience", "How much work experience do you have?", "", "none", True,
                          "Add verified work experience facts with start and end dates."))

    education = drafting._chronological([f for f in facts if f.category == "education"])
    if education:
        top = education[0]
        period = drafting.format_period(top.valid_from, top.valid_until)
        out.append(Answer("education", "Highest or current education", f"{top.subject}" + (f" ({period})" if period else ""),
                          "facts", fact_ids=[top.id]))
    else:
        out.append(Answer("education", "Highest or current education", "", "none", True, "Add verified education facts."))

    job_text = f"{job.title}\n{job.description or ''}"
    matched = [(drafting.skill_name_in(job_text, f), f) for f in facts if f.category == "skill"]
    matched = [(name, f) for name, f in matched if name]
    if matched:
        out.append(Answer("skills", "Your skills for this role", ", ".join(dict.fromkeys(n for n, _ in matched)),
                          "facts", fact_ids=[f.id for _, f in matched]))
    else:
        out.append(Answer("skills", "Your skills for this role", "", "none", True,
                          "None of your verified skills is named in the posting; write this one yourself."))

    links = [f for f in facts if f.category == "contact" and re.search(r"linkedin|github|gitlab|\.io|www\.", f.value_text, re.I)]
    out.append(Answer("links", "LinkedIn, GitHub or portfolio", "\n".join(f"{f.subject}: {f.value_text}" for f in links),
                      "facts" if links else "none", not links, None if links else "Add verified contact facts for your links.",
                      [f.id for f in links]))

    references = [f for f in facts if f.category == "reference"]
    if references:
        out.append(Answer("references", "References", "\n".join(f"{f.subject}: {f.value_text}" for f in references),
                      "facts", fact_ids=[f.id for f in references]))
    else:
        saved_answer("references", "References", "Ask your referees first, then write e.g. “Available on request.”")
    saved_answer("relocation", "Are you willing to relocate?", "Write once, e.g. “Yes, within Finland.”")
    saved_answer("why_us", "Why do you want to work for us?",
                 "Specific to this employer: write it once here (your cover letter's first paragraph is a good start).",
                 store_key=f"why_us:{application.id}")
    return out
