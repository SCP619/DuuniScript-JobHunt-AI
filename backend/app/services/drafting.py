"""Build CV and cover letter drafts from verified profile facts, and check drafts for claims.

Deterministic and local: no language model. Every sentence about the user comes from a
*verified* fact or the user's own profile fields; job text is only used to order facts by
relevance and to name the employer and role. Parts that only the user can write (why this
role) are left as a visible ``[placeholder]`` that blocks approval until replaced.

``check_draft`` runs on generated *and* user-edited text, so edits are held to the same rule:
contact details, years, numbers and technical skills that no verified fact supports are flagged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

GENERATOR_VERSION = "drafts-1"

# ---------- Inputs ----------


@dataclass(frozen=True)
class FactView:
    id: str
    category: str
    subject: str
    value_text: str
    valid_from: date | None = None
    valid_until: date | None = None


@dataclass(frozen=True)
class PersonView:
    display_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    professional_summary: str | None = None


@dataclass(frozen=True)
class JobView:
    title: str
    company: str
    description: str | None = None
    location: str | None = None


@dataclass
class Draft:
    content: str
    evidence: list[str] = field(default_factory=list)


# ---------- Templates ----------


@dataclass(frozen=True)
class Template:
    key: str
    kind: str  # "cv" or "cover_letter"
    name: str
    description: str
    sections: tuple[str, ...] = ()
    max_experience: int | None = None
    max_projects: int | None = None
    max_skills: int | None = None


CV_TEMPLATES = {
    t.key: t
    for t in (
        # Follows the University of Turku career services (Rekry) CV guide: a profile aimed at
        # the job, education then work experience (latest first), positions of trust, language
        # skills with levels, IT skills, references; at most two A4 pages.
        Template(
            "utu_rekry", "cv", "UTU Rekry",
            "The University of Turku career services layout: profile, education, work experience, "
            "positions of trust, languages, IT skills and references. Two pages at most.",
            ("summary", "education", "experience", "projects", "positions", "languages", "it_skills",
             "certifications", "publications", "references"),
            max_experience=5, max_projects=3,
        ),
        Template(
            "utu_rekry_fi", "cv", "UTU Rekry (suomeksi)",
            "The UTU Rekry layout with Finnish headings, for postings in Finnish. Your facts are used as written.",
            ("summary", "education", "experience", "projects", "positions", "languages", "it_skills",
             "certifications", "publications", "references"),
            max_experience=5, max_projects=3,
        ),
        Template(
            "classic", "cv", "Classic",
            "Summary, experience, education, projects, skills and languages. Two pages at most for most profiles.",
            ("summary", "experience", "education", "projects", "skills", "languages", "certifications", "publications"),
            max_projects=4,
        ),
        Template(
            "compact", "cv", "Compact",
            "One page: the skills that match the job first, the three most relevant roles, education and languages.",
            ("summary", "skills", "experience", "education", "languages"),
            max_experience=3, max_projects=0, max_skills=15,
        ),
        Template(
            "projects_first", "cv", "Projects first",
            "For technical roles: the most relevant projects lead, then experience, education and skills.",
            ("summary", "projects", "experience", "education", "skills", "languages", "certifications", "publications"),
            max_projects=5,
        ),
    )
}
LETTER_TEMPLATES = {
    t.key: t
    for t in (
        Template(
            "utu_rekry", "cover_letter", "UTU Rekry",
            "The University of Turku career services layout: date and contact details, the position as a "
            "heading, why this job, how you meet the requirements, an invitation to interview and appendices. One page.",
        ),
        Template(
            "utu_rekry_fi", "cover_letter", "UTU Rekry (suomeksi)",
            "Työhakemus in the UTU Rekry layout with Finnish phrases, for postings in Finnish. Your facts are used as written.",
        ),
        Template(
            "standard", "cover_letter", "Standard",
            "About one page: your most relevant role, the skills the posting asks for, a project, and your own reason for applying.",
        ),
        Template(
            "short", "cover_letter", "Short",
            "Four short paragraphs, for forms with a small text box or an email body.",
        ),
    )
}
MOTIVATION_PLACEHOLDER = "[Write one or two sentences, in your own words, on why this role and this employer interest you.]"

SECTION_TITLES = {
    "summary": "Profile",
    "positions": "Positions of trust",
    "it_skills": "IT skills",
    "references": "References",
    "experience": "Experience",
    "education": "Education",
    "projects": "Projects",
    "skills": "Skills",
    "languages": "Languages",
    "certifications": "Certificates",
    "publications": "Publications",
}
SECTION_TITLES_FI = {
    "summary": "Profiili",
    "positions": "Luottamustehtävät",
    "it_skills": "IT-taidot",
    "references": "Suosittelijat",
    "experience": "Työkokemus",
    "education": "Koulutus",
    "projects": "Projektit",
    "skills": "Taidot",
    "languages": "Kielitaito",
    "certifications": "Sertifikaatit",
    "publications": "Julkaisut",
}
FI_MONTHS = ("tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu", "elokuu",
             "syyskuu", "lokakuu", "marraskuu", "joulukuu")
MOTIVATION_PLACEHOLDER_FI = "[Kirjoita omin sanoin yksi tai kaksi lausetta siitä, miksi juuri tämä tehtävä ja työnantaja kiinnostavat sinua.]"


def is_finnish(template_key: str | None) -> bool:
    return bool(template_key and template_key.endswith("_fi"))


def format_period_fi(start: date | None, end: date | None) -> str:
    fmt = lambda d: f"{d.month}/{d.year}"  # noqa: E731
    if start and end:
        if start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31:
            return str(start.year) if start.year == end.year else f"{start.year}–{end.year}"
        return f"{fmt(start)}–{fmt(end)}"
    if start:
        return f"{fmt(start)} alkaen"
    if end:
        return f"{fmt(end)} asti"
    return ""


SECTION_CATEGORIES = {
    "experience": "work_experience",
    "education": "education",
    "projects": "project",
    "skills": "skill",
    "it_skills": "skill",
    "references": "reference",
    "languages": "language",
    "certifications": "certification",
    "publications": "publication",
}

# ---------- Text helpers ----------

STOPWORDS = set(
    "the and for with you your our are will have has this that from into able work working role team teams "
    "about their they them who what when where which while also more most other such than then there these "
    "those very can may must should would could all any each per via etc job jobs position company we us "
    "experience years year skills skill knowledge strong good great excellent including include new using use "
    "ja tai sekä on ovat olla että kanssa joka jotka myös".split()
)
_WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]*[a-z0-9+#]|[a-z0-9]", re.IGNORECASE)


def words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "") if len(w) >= 3 and w.lower() not in STOPWORDS}


def contains_phrase(text: str, phrase: str) -> bool:
    phrase = phrase.strip()
    if not phrase:
        return False
    return re.search(rf"(?<![\w]){re.escape(phrase)}(?![\w])", text, re.IGNORECASE) is not None


def format_period(start: date | None, end: date | None) -> str:
    fmt = lambda d: d.strftime("%b %Y")  # noqa: E731
    if start and end:
        if start.year == end.year and start.month == 1 and end.month == 12 and end.day == 31:
            return str(start.year)
        if start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31:
            return f"{start.year} – {end.year}"
        return f"{fmt(start)} – {fmt(end)}"
    if start:
        return f"Since {fmt(start)}"
    if end:
        return f"Until {fmt(end)}"
    return ""


def _description(fact: FactView) -> str:
    """The fact text without the subject it starts with (the parser stores "subject. details")."""
    text = fact.value_text.strip()
    for prefix in (fact.subject + ". ", fact.subject + ": ", fact.subject):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text


def _sentences(text: str) -> list[str]:
    return [m.strip() for m in re.findall(r".+?(?:[.!?](?=\s|$)|$)", text.strip()) if m.strip()]


def _first_sentence(text: str) -> str:
    """The first sentence that reads as prose: metadata ("Hackathon · Lead developer") and links are skipped."""
    sentences = _sentences(text)
    for sentence in sentences:
        if " · " not in sentence and not re.search(r"[\w-]+\.(?:com|io|fi|org)/", sentence):
            return sentence
    return sentences[0] if sentences else ""


def _join_words(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---------- Relevance ----------


def skill_name_in(job_text: str, fact: FactView) -> str | None:
    """How the posting names this skill: the whole skill, or a known technical term inside it.

    "Analysis SQL" (a CV label followed by a skill) matches a posting asking for "SQL".
    """
    if contains_phrase(job_text, fact.subject):
        return fact.subject
    for term in TECH_TERMS:
        if contains_phrase(fact.subject, term) and contains_phrase(job_text, term):
            return term
    return None


def relevance(fact: FactView, job_text: str, job_words: set[str]) -> float:
    if fact.category == "skill":
        return 3.0 if skill_name_in(job_text, fact) else 0.0
    fact_words = words(f"{fact.subject} {fact.value_text}")
    if not fact_words:
        return 0.0
    overlap = len(fact_words & job_words)
    return overlap / (len(fact_words) ** 0.5)


def _ranked(facts: list[FactView], category: str, job_text: str, job_words: set[str]) -> list[tuple[float, FactView]]:
    chosen = [f for f in facts if f.category == category]
    return sorted(
        ((relevance(f, job_text, job_words), f) for f in chosen),
        key=lambda pair: (-pair[0], pair[1].subject.lower()),
    )


def _chronological(items: list[FactView]) -> list[FactView]:
    # Ongoing first, then by end date, then start date, newest first.
    return sorted(
        items,
        key=lambda f: (f.valid_until is None and f.valid_from is not None, f.valid_until or date.min, f.valid_from or date.min),
        reverse=True,
    )


# ---------- CV ----------


def contact_line(person: PersonView, facts: list[FactView]) -> tuple[str, list[str]]:
    parts: list[str] = []
    used: list[str] = []
    if person.location:
        parts.append(person.location)
    if person.email:
        parts.append(person.email)
    if person.phone:
        parts.append(person.phone)
    for fact in facts:
        if fact.category != "contact":
            continue
        value = fact.value_text.strip()
        if any(value.lower() == p.lower() for p in parts):
            continue
        parts.append(value)
        used.append(fact.id)
    return " · ".join(parts), used


def build_cv(
    person: PersonView, facts: list[FactView], job: JobView, template_key: str, today: date | None = None,
    focus: list[str] | None = None,
) -> Draft:
    """``focus``: words from a CV profile; facts mentioning them rank higher (nothing is added)."""
    template = CV_TEMPLATES[template_key]
    job_text = f"{job.title}\n{job.description or ''}" + ("\n" + "\n".join(focus) * 2 if focus else "")
    job_words = words(job_text)
    lines: list[str] = [f"# {person.display_name}"]
    contact, evidence = contact_line(person, facts)
    if contact:
        lines.append(contact)
    finnish = is_finnish(template.key)
    if template.key == "utu_rekry":
        lines.append(f"*Curriculum Vitae · {(today or date.today()).strftime('%d %B %Y').lstrip('0')}*")
    elif finnish:
        day = today or date.today()
        lines.append(f"*Ansioluettelo · {day.day}.{day.month}.{day.year}*")
    for section in template.sections:
        body, used = _cv_section(section, template, person, facts, job_text, job_words)
        if body:
            titles = SECTION_TITLES_FI if finnish else SECTION_TITLES
            lines += ["", f"## {titles[section]}", *body]
            evidence += used
    return Draft("\n".join(lines).strip() + "\n", _unique(evidence))


def _cv_section(
    section: str,
    template: Template,
    person: PersonView,
    facts: list[FactView],
    job_text: str,
    job_words: set[str],
) -> tuple[list[str], list[str]]:
    if section == "summary":
        summaries = [f for f in facts if f.category == "summary"]
        if summaries:
            return [summaries[0].value_text.strip()], [summaries[0].id]
        if person.professional_summary:
            return [person.professional_summary.strip()], []
        return [], []

    if section == "positions":
        chosen = [f for f in facts if f.category in ("achievement", "other") and POSITION_OF_TRUST.search(f"{f.subject} {f.value_text}")]
        body = []
        for fact in _chronological(chosen):
            period = format_period(fact.valid_from, fact.valid_until)
            body.append(f"- {fact.subject}" + (f" ({period})" if period else ""))
        return body, [f.id for f in chosen]

    category = SECTION_CATEGORIES[section]
    ranked = _ranked(facts, category, job_text, job_words)
    if not ranked:
        return [], []

    if section == "references":
        return [f"- {f.subject}: {_description(f) or f.value_text}" for _, f in ranked], [f.id for _, f in ranked]

    if section in ("skills", "it_skills"):
        limit = template.max_skills
        chosen = [f for _, f in ranked][: limit or None]
        return [", ".join(f.subject for f in chosen)], [f.id for f in chosen]

    if section == "languages":
        chosen = [f for _, f in ranked]
        return [f"- {f.value_text.strip()}" for f in chosen], [f.id for f in chosen]

    limit = template.max_experience if section == "experience" else template.max_projects if section == "projects" else None
    if limit == 0:
        return [], []
    chosen = [f for _, f in ranked][: limit or None]
    if section in ("experience", "education"):
        chosen = _chronological(chosen)
    body: list[str] = []
    for fact in chosen:
        body += ["", f"### {fact.subject}"]
        period = (format_period_fi if is_finnish(template.key) else format_period)(fact.valid_from, fact.valid_until)
        if period:
            body.append(f"*{period}*")
        description = _description(fact)
        if description:
            body.append(description)
    return body, [f.id for f in chosen]


POSITION_OF_TRUST = re.compile(
    r"\b(board|member|chair|committee|council|representative|volunteer|trustee|treasurer|secretary|"
    r"hallitus|jäsen|puheenjohtaja|edustaja)\b",
    re.IGNORECASE,
)

# ---------- Cover letter ----------

PAST_VERBS = {
    "led", "ran", "built", "wrote", "made", "taught", "won", "drove", "grew", "set", "sold",
    "managed", "designed", "developed", "delivered", "analysed", "analyzed", "created", "implemented", "launched",
}


def _as_i_sentence(sentence: str) -> str | None:
    first = sentence.split()[0].lower() if sentence.split() else ""
    if first in PAST_VERBS or (first.endswith("ed") and len(first) > 4):
        return "I " + sentence[0].lower() + sentence[1:]
    return None


def _role_and_org(subject: str) -> tuple[str, str | None]:
    parts = [p.strip() for p in re.split(r"\s+[·|]\s+|\s+at\s+", subject) if p.strip()]
    if len(parts) >= 2:
        org = re.split(r",|\.\s", parts[1])[0].strip()
        return parts[0], org or None
    return subject, None


def build_cover_letter(
    person: PersonView, facts: list[FactView], job: JobView, template_key: str, today: date
) -> Draft:
    template = LETTER_TEMPLATES[template_key]
    if template.key == "utu_rekry":
        return _utu_letter(person, facts, job, today)
    if template.key == "utu_rekry_fi":
        return _utu_letter_fi(person, facts, job, today)
    job_text = f"{job.title}\n{job.description or ''}"
    job_words = words(job_text)
    evidence: list[str] = []

    header = [person.display_name]
    contact = " · ".join(p for p in (person.email, person.phone, person.location) if p)
    if contact:
        header.append(contact)
    header += ["", today.strftime("%d %B %Y").lstrip("0"), "", job.company, f"Re: {job.title}", ""]

    paragraphs = [f"Dear hiring team at {job.company},"]
    opening = f"I am applying for the {job.title} position at {job.company}."
    summaries = [f for f in facts if f.category == "summary"]
    if summaries:
        summary = _first_sentence(summaries[0].value_text)
        opening += " " + (summary if summary.split()[0] in ("I", "I'm", "My") else f"In short: {summary}")
        evidence.append(summaries[0].id)
    paragraphs.append(opening)

    experience = [f for score, f in _ranked(facts, "work_experience", job_text, job_words)]
    if experience:
        top = experience[0]
        role, org = _role_and_org(top.subject)
        period = format_period(top.valid_from, top.valid_until)
        where = f" at {org}" if org else ""
        when = f" ({period})" if period else ""
        sentence = _first_sentence(_description(top))
        i_sentence = _as_i_sentence(sentence) if sentence else None
        if i_sentence:
            text = f"In my role as {role}{where}{when}, {i_sentence}"
        elif sentence:
            text = f"In my role as {role}{where}{when}: {sentence}"
        else:
            text = f"Most recently I worked as {role}{where}{when}."
        paragraphs.append(text)
        evidence.append(top.id)

    matched = [f for score, f in _ranked(facts, "skill", job_text, job_words) if score > 0]
    if matched:
        names = list(dict.fromkeys(skill_name_in(job_text, f) or f.subject for f in matched[:6]))
        paragraphs.append(
            f"Your posting asks for {_join_words(names)}; {'these are' if len(names) > 1 else 'this is'} among the skills in my CV."
        )
        evidence += [f.id for f in matched[:6]]

    if template.key == "standard":
        projects = [(s, f) for s, f in _ranked(facts, "project", job_text, job_words) if s > 0]
        if projects:
            project = projects[0][1]
            detail = _first_sentence(_description(project))
            name = project.subject.split(" · ")[0]
            paragraphs.append(f"A relevant project is {name}: {detail}" if detail else f"A relevant project is {name}.")
            evidence.append(project.id)
        language_needed = [n for n in ("Finnish", "Swedish", "English") if contains_phrase(job_text, n)]
        languages = [f for f in facts if f.category == "language" and any(n.lower() in f.subject.lower() for n in language_needed)]
        if languages:
            paragraphs.append("Languages: " + "; ".join(f.value_text.strip() for f in languages) + ".")
            evidence += [f.id for f in languages]

    paragraphs.append(MOTIVATION_PLACEHOLDER)
    paragraphs.append(
        f"Thank you for considering my application. I would welcome the chance to discuss how I could contribute to {job.company}."
    )
    paragraphs.append(f"Kind regards,\n{person.display_name}")
    content = "\n".join(header) + "\n" + "\n\n".join(paragraphs) + "\n"
    return Draft(content, _unique(evidence))


def _experience_sentence(facts: list[FactView], job_text: str, job_words: set[str]) -> tuple[str | None, str | None]:
    experience = [f for _, f in _ranked(facts, "work_experience", job_text, job_words)]
    if not experience:
        return None, None
    top = experience[0]
    role, org = _role_and_org(top.subject)
    period = format_period(top.valid_from, top.valid_until)
    where = f" at {org}" if org else ""
    when = f" ({period})" if period else ""
    sentence = _first_sentence(_description(top))
    i_sentence = _as_i_sentence(sentence) if sentence else None
    if i_sentence:
        return f"As {role}{where}{when}, {i_sentence}", top.id
    if sentence:
        return f"As {role}{where}{when}, my work included the following: {sentence}", top.id
    return f"Most recently I worked as {role}{where}{when}.", top.id


UTU_CLOSING = "I would be glad to tell you more about my experience and motivation in an interview."
UTU_APPENDICES = "Appendices: CV\nCopies of certificates available when requested"


def _utu_letter(person: PersonView, facts: list[FactView], job: JobView, today: date) -> Draft:
    """Cover letter in the University of Turku career services (Rekry) layout. About one page."""
    job_text = f"{job.title}\n{job.description or ''}"
    job_words = words(job_text)
    evidence: list[str] = []
    contact = " · ".join(p for p in (person.email, person.phone, person.location) if p)
    lines = [f"Job application · {today.strftime('%d %B %Y').lstrip('0')}", "", person.display_name]
    if contact:
        lines.append(contact)
    lines += ["", job.company, "Recruitment team", "", f"## {job.title}", ""]

    paragraphs = [MOTIVATION_PLACEHOLDER]
    matched = [f for score, f in _ranked(facts, "skill", job_text, job_words) if score > 0]
    experience, top_id = _experience_sentence(facts, job_text, job_words)
    fit = []
    if matched:
        names = list(dict.fromkeys(skill_name_in(job_text, f) or f.subject for f in matched[:6]))
        fit.append(f"The position calls for {_join_words(names)}, and I have used {'them' if len(names) > 1 else 'it'} in my own work.")
        evidence += [f.id for f in matched[:6]]
    if experience:
        fit.append(experience)
        evidence.append(top_id)
    if fit:
        paragraphs.append(" ".join(fit))

    # The guide: the letter should not repeat the CV, so the CV's profile text is not copied here.
    present = []
    projects = [(s, f) for s, f in _ranked(facts, "project", job_text, job_words) if s > 0]
    if projects:
        project = projects[0][1]
        detail = _first_sentence(_description(project))
        name = project.subject.split(" · ")[0]
        present.append(f"A recent example of my work is {name}: {detail}" if detail else f"A recent example of my work is {name}.")
        evidence.append(project.id)
    language_needed = [n for n in ("Finnish", "Swedish", "English") if contains_phrase(job_text, n)]
    languages = [f for f in facts if f.category == "language" and any(n.lower() in f.subject.lower() for n in language_needed)]
    if languages:
        present.append("My language skills: " + "; ".join(f.value_text.strip() for f in languages) + ".")
        evidence += [f.id for f in languages]
    if present:
        paragraphs.append(" ".join(present))

    paragraphs.append(UTU_CLOSING)
    paragraphs.append(f"Yours sincerely,\n{person.display_name}")
    paragraphs.append(UTU_APPENDICES)
    content = "\n".join(lines) + "\n" + "\n\n".join(paragraphs) + "\n"
    return Draft(content, _unique(evidence))


UTU_CLOSING_FI = "Kerron mielelläni lisää osaamisestani ja motivaatiostani haastattelussa."
UTU_APPENDICES_FI = "Liitteet: CV\nTodistusjäljennökset pyydettäessä"


def _utu_letter_fi(person: PersonView, facts: list[FactView], job: JobView, today: date) -> Draft:
    """Työhakemus in the UTU Rekry layout. Facts are quoted as written (not translated)."""
    job_text = f"{job.title}\n{job.description or ''}"
    job_words = words(job_text)
    evidence: list[str] = []
    contact = " · ".join(p for p in (person.email, person.phone, person.location) if p)
    lines = [f"Työhakemus · {today.day}.{today.month}.{today.year}", "", person.display_name]
    if contact:
        lines.append(contact)
    lines += ["", job.company, "Rekrytointi", "", f"## {job.title}", ""]
    paragraphs = [MOTIVATION_PLACEHOLDER_FI]
    fit = []
    matched = [f for score, f in _ranked(facts, "skill", job_text, job_words) if score > 0]
    if matched:
        names = list(dict.fromkeys(skill_name_in(job_text, f) or f.subject for f in matched[:6]))
        fit.append(f"Tehtävässä tarvitaan osaamista, jota minulla on: {_join_words(names).replace(' and ', ' ja ')}.")
        evidence += [f.id for f in matched[:6]]
    experience = [f for _, f in _ranked(facts, "work_experience", job_text, job_words)]
    if experience:
        top = experience[0]
        role, org = _role_and_org(top.subject)
        period = format_period_fi(top.valid_from, top.valid_until)
        where = f", {org}" if org else ""
        when = f" ({period})" if period else ""
        fit.append(f"Viimeisin relevantti työkokemukseni: {role}{where}{when}.")
        evidence.append(top.id)
    if fit:
        paragraphs.append(" ".join(fit))
    projects = [(sc, f) for sc, f in _ranked(facts, "project", job_text, job_words) if sc > 0]
    if projects:
        name = projects[0][1].subject.split(" · ")[0]
        paragraphs.append(f"Esimerkki työstäni on projekti {name}.")
        evidence.append(projects[0][1].id)
    languages = [f for f in facts if f.category == "language"]
    if languages:
        paragraphs.append("Kielitaitoni: " + "; ".join(f.value_text.strip() for f in languages) + ".")
        evidence += [f.id for f in languages]
    paragraphs.append(UTU_CLOSING_FI)
    paragraphs.append(f"Ystävällisin terveisin\n{person.display_name}")
    paragraphs.append(UTU_APPENDICES_FI)
    content = "\n".join(lines) + "\n" + "\n\n".join(paragraphs) + "\n"
    return Draft(content, _unique(evidence))


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


# ---------- Claim checks ----------

# Technical terms checked in drafts. A term in a draft must appear in a verified fact.
TECH_TERMS = (
    "Python", "Java", "JavaScript", "TypeScript", "SQL", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis",
    "React", "Angular", "Vue", "Svelte", "Next.js", "Node.js", "Django", "Flask", "FastAPI", "Spring",
    "Kotlin", "Swift", "C++", "C#", ".NET", "Rust", "PHP", "Ruby", "Scala", "MATLAB", "SAS", "SPSS",
    "Excel", "Power BI", "Tableau", "Looker", "Qlik", "AWS", "Azure", "GCP", "Google Cloud", "Docker",
    "Kubernetes", "Terraform", "Ansible", "Linux", "Spark", "Hadoop", "Kafka", "Airflow", "dbt", "Snowflake",
    "Databricks", "BigQuery", "Redshift", "DuckDB", "Pandas", "NumPy", "TensorFlow", "PyTorch", "Keras",
    "scikit-learn", "Machine learning", "Deep learning", "NLP", "Computer vision", "LLM", "GA4",
    "Google Analytics", "Mixpanel", "PostHog", "Twilio Segment", "SAP", "Salesforce", "HubSpot", "Figma", "Jira",
    "Scrum", "CI/CD", "GraphQL", "HTML", "CSS", "Flutter", "Android", "iOS", "Unity", "Git", "Bash",
    "PowerShell", "Selenium", "Playwright", "Cypress", "OpenCV", "YOLO", "Elasticsearch", "Grafana",
)

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w/])(?:\(\+\d{1,4}\)|\+\d)[\d\s()-]{6,18}\d")
LINK = re.compile(r"\b(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|fi|io|org|net|dev|me)(?:/[^\s)]*)?", re.IGNORECASE)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?\s?%|(?<![\w./+-])\d{2,}(?:[.,]\d+)*(?![\w/])")
PLACEHOLDER = re.compile(r"\[[^\]\n]{3,}\]")
LETTER_DATE = re.compile(
    r"^\s*\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:19|20)\d{2}\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" blocks approval; "warning" needs acknowledgement; "info" is advice
    code: str
    message: str
    excerpt: str | None = None


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _normal_sentences(text: str) -> dict[str, str]:
    found = {}
    for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
        sentence = raw.strip().lstrip("-#* ").strip()
        key = re.sub(r"[^\w]+", " ", sentence.lower()).strip()
        if len(key) >= 40:
            found[key] = sentence
    return found


def shared_sentences(a: str, b: str) -> list[str]:
    """Sentences (40+ characters) that appear in both texts, ignoring case and punctuation."""
    left, right = _normal_sentences(a), _normal_sentences(b)
    shared = [left[k] for k in left if k in right or any(k in r for r in right)]
    return shared[:5]


def check_draft(content: str, person: PersonView, facts: list[FactView], job: JobView, today: date) -> list[Issue]:
    issues: list[Issue] = []
    support = "\n".join(
        [f"{f.subject}\n{f.value_text}" for f in facts]
        + [person.display_name, person.email or "", person.phone or "", person.location or "", person.professional_summary or ""]
    )
    years_ok = set(YEAR.findall(support)) | {str(today.year)}
    for f in facts:
        for d in (f.valid_from, f.valid_until):
            if d:
                years_ok.add(str(d.year))
    employer = f"{job.title}\n{job.company}"
    years_ok |= set(YEAR.findall(employer))

    for match in PLACEHOLDER.finditer(content):
        issues.append(Issue("error", "placeholder_left", "Replace the text in square brackets before approving.", match.group(0)[:200]))

    known_emails = {e.lower() for e in EMAIL.findall(support)}
    for email in set(EMAIL.findall(content)):
        if email.lower() not in known_emails:
            issues.append(Issue("error", "unknown_contact", "This email address is not in your profile or verified facts.", email))
    known_phones = {_digits(p) for p in PHONE.findall(support)}
    for phone in set(PHONE.findall(content)):
        if _digits(phone) not in known_phones:
            issues.append(Issue("error", "unknown_contact", "This phone number is not in your profile or verified facts.", phone.strip()))
    support_lower = support.lower()
    for link in set(LINK.findall(content)):
        bare = re.sub(r"^(?:https?://)?(?:www\.)?", "", link.lower()).rstrip("/.")
        if "@" in link or EMAIL.search(link):
            continue
        if bare not in support_lower and not contains_phrase(employer, bare):
            issues.append(Issue("warning", "unsupported_link", "This web address is not in your verified facts.", link))

    text_without_contacts = EMAIL.sub(" ", PHONE.sub(" ", content))
    # The letter's own date ("10 November 2026") is not a claim.
    text_without_contacts = LETTER_DATE.sub(" ", text_without_contacts)
    # Today's date in the CV or letter header is not a claim either.
    text_without_contacts = text_without_contacts.replace(today.strftime("%d %B %Y").lstrip("0"), " ")
    text_without_contacts = text_without_contacts.replace(f"{today.day}.{today.month}.{today.year}", " ")
    for year in sorted(set(YEAR.findall(text_without_contacts)) - years_ok):
        issues.append(Issue("warning", "unsupported_date", "No verified fact mentions this year.", year))
    support_numbers = {n.replace(" ", "") for n in NUMBER.findall(support + "\n" + employer)}
    for number in sorted({n.replace(" ", "") for n in NUMBER.findall(YEAR.sub(" ", text_without_contacts))}):
        if number not in support_numbers and _digits(number) not in {_digits(n) for n in support_numbers}:
            issues.append(Issue("warning", "unsupported_number", "No verified fact contains this number.", number))

    for term in TECH_TERMS:
        if contains_phrase(content, term) and not contains_phrase(support, term) and not contains_phrase(employer, term):
            issues.append(Issue("warning", "unsupported_skill", f"No verified fact mentions {term}.", term))

    job_text = f"{job.title}\n{job.description or ''}"
    missing = [t for t in TECH_TERMS if contains_phrase(job_text, t) and not contains_phrase(support, t)]
    if missing:
        issues.append(
            Issue(
                "info",
                "job_terms_not_in_profile",
                "The posting mentions these, and none of your verified facts do: " + ", ".join(missing[:15]) + ".",
            )
        )
    for language in ("Finnish", "Swedish"):
        if contains_phrase(job_text, language) and not any(
            f.category == "language" and language.lower() in f.subject.lower() for f in facts
        ):
            issues.append(
                Issue("info", "language_not_in_profile", f"The posting mentions {language}; you have no verified {language} language fact.")
            )
    return issues
