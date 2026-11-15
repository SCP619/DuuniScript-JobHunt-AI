"""Job relevance: a transparent 0-100 match score with reasons (PRD FR-008).

Rule-based and local. Only *verified* facts count. The score is a ranking aid, not a judgement
of eligibility: matched skills, missing requirements and blockers are listed so the user decides.

Score parts (scoring version ``match-1``):
- Skills (60): technical terms and skills the posting names that a verified fact covers
  (divided by at least 4, so a posting naming one or two terms cannot give full points).
- Role (25): how close the job title is to a verified role, degree or target-role preference.
- Wording (15): overlap between the posting's words and the verified facts.
- Your decisions (±10): job titles that resemble jobs you marked "not relevant" go down,
  titles like those you saved, drafted or applied to go up (from 3 decisions on).
- Meaning (up to +20, rescaled): with the local embedding model, how close the posting is in
  meaning to your verified facts (``rag_service``).
- Learned (±10): a reward model trained on your decisions and outcomes (``preference_model``).
Blockers cap the score at 30: the job is not open to people in Finland, its deadline has
passed, or it requires a language (Finnish, Swedish) the verified facts do not show at a
working level.

Scores are stored in ``job_match`` with a fingerprint of the verified facts and of the job,
and recomputed lazily when either changes (or the day changes, for deadlines).
"""

from __future__ import annotations

import hashlib
import re
import threading
from datetime import date

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.persistence.models import Job, JobMatch, ProfileFact, VerificationStatus, utcnow
from app.services import drafting
from app.services.profile_service import get_profile

SCORING_VERSION = "match-3"
# One recompute at a time: the UI asks for several job lists at once on page load.
_REFRESH_LOCK = threading.Lock()
BLOCKER_CAP = 30

LANGUAGE_NAMES = {
    "Finnish": ("finnish", "suomen kiel", "suomea", "suomi"),
    "Swedish": ("swedish", "ruotsin kiel", "ruotsia", "svenska"),
}
REQUIRED = re.compile(
    r"required|requirement|must|fluent|fluency|native|excellent|good command|vaaditaan|edellytämme|"
    r"edellytetään|sujuva|erinomai|hyvä"
)
OPTIONAL = re.compile(r"\bplus\b|advantage|eduksi|bonus|nice to have|a merit|ansioksi|is an asset|preferred")
WORKING_LEVEL = re.compile(r"native|mother tongue|fluent|\bc1\b|\bc2\b|\bb2\b|äidinkieli|sujuva|erinomai|professional", re.IGNORECASE)
USEFUL = ("skill", "work_experience", "project", "education", "summary", "certification", "preference")


def fingerprint(facts: list[ProfileFact], today: date, feedback: Feedback | None = None, extra: str = "") -> str:
    parts = sorted(f"{f.id}|{f.updated_at.isoformat()}" for f in facts)
    decisions = sorted(f"{job_id}|{status}" for job_id, (status, _) in (feedback.decided.items() if feedback else []))
    payload = "\n".join([SCORING_VERSION, today.isoformat(), *parts, "--", *decisions, "--", extra])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def job_hash(job: Job, has_vector: bool = False) -> str:
    return f"{job.content_hash}:{job.available_from_finland}:{int(job.apply_manually)}:{'v' if has_vector else '-'}"


def _outcomes(session: Session) -> dict[str, str]:
    from app.persistence.models import Application

    rows = session.execute(select(Application.job_id, Application.outcome).where(Application.outcome.is_not(None))).all()
    return {job_id: outcome for job_id, outcome in rows}


def _views(facts: list[ProfileFact]) -> list[drafting.FactView]:
    return [drafting.FactView(f.id, f.category, f.subject, f.value_text, f.valid_from, f.valid_until) for f in facts]


def _role_words(facts: list[drafting.FactView]) -> list[set[str]]:
    roles = []
    for fact in facts:
        if fact.category in ("work_experience", "preference"):
            roles.append(drafting.words(re.split(r"\s+[·|]\s+|\s+at\s+", fact.subject)[0]))
            if fact.category == "preference":
                roles.append(drafting.words(fact.value_text))
        elif fact.category == "education":
            roles.append(drafting.words(fact.subject))
        elif fact.category == "summary":
            roles.append(drafting.words(" ".join(fact.value_text.split()[:6])))
    return [r for r in roles if r]


def language_requirements(job_text: str) -> list[str]:
    """Languages the posting asks for as a requirement (not "an advantage")."""
    found = []
    lowered = job_text.lower()
    for language, names in LANGUAGE_NAMES.items():
        for name in names:
            hit = False
            for match in re.finditer(re.escape(name), lowered):
                window = lowered[max(0, match.start() - 80): match.end() + 80]
                if REQUIRED.search(window) and not OPTIONAL.search(window):
                    hit = True
                    break
            if hit:
                found.append(language)
                break
    return found


POSITIVE = ("saved", "drafting", "applied")
NEGATIVE = ("not_relevant",)
MIN_DECISIONS = 3
FEEDBACK_POINTS = 10


class Feedback:
    """Title words of jobs the user decided on: liked (saved/drafting/applied) or not relevant."""

    def __init__(self, decided: list[tuple[str, str, str]]) -> None:  # (job id, status, title)
        from collections import Counter

        self.decided = {job_id: (status, drafting.words(title)) for job_id, status, title in decided}
        self.positive: Counter[str] = Counter()
        self.negative: Counter[str] = Counter()
        for status, words in self.decided.values():
            (self.positive if status in POSITIVE else self.negative).update(words)

    @property
    def active(self) -> bool:
        return len(self.decided) >= MIN_DECISIONS

    def adjust(self, job: Job) -> tuple[int, str | None]:
        if not self.active:
            return 0, None
        own = self.decided.get(job.id)  # a job's own decision does not score itself
        title = drafting.words(job.title)
        if not title:
            return 0, None
        total = 0.0
        liked, disliked = [], []
        for word in title:
            pos = self.positive[word] - (1 if own and own[0] in POSITIVE and word in own[1] else 0)
            neg = self.negative[word] - (1 if own and own[0] in NEGATIVE and word in own[1] else 0)
            if pos or neg:
                total += (pos - neg) / (pos + neg + 1)
                (liked if pos > neg else disliked if neg > pos else []).append(word)
        points = max(-FEEDBACK_POINTS, min(FEEDBACK_POINTS, round(FEEDBACK_POINTS * total / len(title))))
        if points > 0:
            return points, f"Similar to jobs you saved or applied to ({', '.join(sorted(liked)[:4])}): +{points}."
        if points < 0:
            return points, f"Similar to jobs you marked not relevant ({', '.join(sorted(disliked)[:4])}): {points}."
        return 0, None


def load_feedback(session: Session) -> Feedback:
    rows = session.execute(
        select(Job.id, Job.status, Job.title).where(Job.status.in_(POSITIVE + NEGATIVE))
    ).all()
    return Feedback([(r[0], r[1], r[2]) for r in rows])


SEMANTIC_LOW, SEMANTIC_HIGH, SEMANTIC_POINTS = 0.35, 0.70, 20


def semantic_points(similarity: float | None) -> int | None:
    if similarity is None:
        return None
    return round(SEMANTIC_POINTS * max(0.0, min(1.0, (similarity - SEMANTIC_LOW) / (SEMANTIC_HIGH - SEMANTIC_LOW))))


def score_job(job: Job, facts: list[drafting.FactView], today: date, feedback: Feedback | None = None,
              similarity: float | None = None) -> tuple[int | None, dict]:
    if not any(f.category in USEFUL for f in facts):
        return None, {
            "reasons": ["Verify some profile facts to see how well jobs match."],
            "matched_skills": [], "missing_terms": [], "blockers": [], "parts": {},
        }
    job_text = f"{job.title}\n{job.description or ''}"
    support = "\n".join(f"{f.subject}\n{f.value_text}" for f in facts)

    matched: list[str] = []

    def add(name: str) -> None:
        if name.lower() not in {m.lower() for m in matched}:
            matched.append(name)

    for fact in facts:
        if fact.category == "skill":
            name = drafting.skill_name_in(job_text, fact)
            if name:
                add(name)
    requested = [t for t in drafting.TECH_TERMS if drafting.contains_phrase(job_text, t)]
    for term in requested:
        if drafting.contains_phrase(support, term):
            add(term)
    missing = [t for t in requested if t.lower() not in {m.lower() for m in matched}]
    wanted = len({t.lower() for t in requested} | {m.lower() for m in matched})

    title_words = drafting.words(job.title)
    roles = _role_words(facts)
    role_ratio = max((len(title_words & r) / len(title_words) for r in roles), default=0.0) if title_words else 0.0

    job_words = drafting.words(job_text)
    overlap = min(1.0, len(job_words & drafting.words(support)) / max(1.0, len(job_words) ** 0.5 * 2.5))

    # Fewer than four named skills is thin evidence: one matching term is not 60 points.
    skill_points = 60 * len(matched) / max(wanted, 4) if wanted else 40 * (role_ratio + overlap) / 2
    role_points = 25 * role_ratio
    wording_points = 15 * overlap
    feedback_points, feedback_reason = feedback.adjust(job) if feedback else (0, None)
    score = round(skill_points + role_points + wording_points) + feedback_points
    meaning = semantic_points(similarity)
    if meaning is not None:
        # Rescale so the maximum stays 100 with the extra meaning-based part.
        score = round((score + meaning) * 100 / (100 + SEMANTIC_POINTS))

    blockers: list[dict] = []
    if job.available_from_finland == "no":
        blockers.append({"code": "not_open_to_finland", "message": "This job is limited to other countries."})
    if job.deadline_on and job.deadline_on < today:
        blockers.append({"code": "deadline_passed", "message": f"The deadline ({job.deadline_on.isoformat()}) has passed."})
    for language in language_requirements(job_text):
        levels = [f for f in facts if f.category == "language" and language.lower() in f.subject.lower()]
        if not any(WORKING_LEVEL.search(f.value_text) for f in levels):
            blockers.append({
                "code": "language_required",
                "message": f"The posting asks for {language}; your verified facts do not show it at a working level.",
            })
    if blockers:
        score = min(score, BLOCKER_CAP)

    reasons: list[str] = []
    if wanted:
        reasons.append(
            f"Matches {len(matched)} of {wanted} skills the posting names"
            + (f": {', '.join(matched[:8])}." if matched else ".")
        )
    else:
        reasons.append("The posting names no technical skills; scored on the job title and wording.")
    if role_ratio >= 0.5:
        reasons.append("The job title is close to a role, degree or target role in your verified facts.")
    if missing:
        reasons.append("Not in your verified facts: " + ", ".join(missing[:8]) + ".")
    if meaning is not None:
        level = "high" if meaning >= 14 else "medium" if meaning >= 7 else "low"
        reasons.append(f"Closeness in meaning to your verified facts: {level} ({meaning}/{SEMANTIC_POINTS}).")
    if feedback_reason:
        reasons.append(feedback_reason)
    reasons += [b["message"] for b in blockers]
    details = {
        "reasons": reasons,
        "matched_skills": matched,
        "missing_terms": missing,
        "blockers": blockers,
        "parts": {"skills": round(skill_points), "role": round(role_points), "wording": round(wording_points),
                  "feedback": feedback_points, "semantic": meaning},
        "similarity": similarity,
    }
    return max(0, min(100, score)), details


def verified_facts(session: Session) -> list[ProfileFact]:
    profile = get_profile(session)
    if profile is None:
        return []
    return list(
        session.scalars(
            select(ProfileFact).where(
                ProfileFact.profile_id == profile.id,
                ProfileFact.verification_status == VerificationStatus.VERIFIED.value,
            )
        )
    )


_APP_LLM: dict = {}  # set by the app at start-up so every caller uses the same local model


def refresh(session: Session, today: date | None = None, llm=None) -> int:  # noqa: ANN001
    """Recompute missing or stale scores. Returns how many were computed.

    Serialised with a lock; the session's view is refreshed inside it so rows written by a
    request that held the lock first are seen (no duplicate inserts).
    """
    with _REFRESH_LOCK:
        session.commit()  # end any read transaction so the lookup below sees committed rows
        return _refresh(session, today or date.today(), llm or _APP_LLM.get("llm"))


def _refresh(session: Session, today: date, llm=None) -> int:  # noqa: ANN001
    from app.services import preference_model, rag_service

    facts = verified_facts(session)
    feedback = load_feedback(session)
    embed_model = llm.embed_model if llm is not None and getattr(llm, "embed_model", None) else None
    fact_vecs = rag_service.fact_vectors(session, embed_model)
    outcomes = _outcomes(session)
    job_vec_count = len(rag_service.job_vectors(session, embed_model)) if fact_vecs else 0
    fp = fingerprint(facts, today, feedback,
                     extra=f"emb:{embed_model}:{len(fact_vecs)}:{job_vec_count}|out:{sorted(outcomes.items())}")
    rows = session.execute(
        select(Job, JobMatch)
        .outerjoin(JobMatch, JobMatch.job_id == Job.id)
        .where(
            or_(
                JobMatch.job_id.is_(None),
                JobMatch.profile_fingerprint != fp,
                JobMatch.job_hash.not_like(
                    Job.content_hash + ":" + Job.available_from_finland + ":" + cast(Job.apply_manually, String) + ":%"
                ),
                JobMatch.scoring_version != SCORING_VERSION,
            )
        )
    ).all()
    if not rows:
        return 0
    views = _views(facts)
    now = utcnow()
    job_vecs = rag_service.job_vectors(session, embed_model, [job.id for job, _ in rows]) if fact_vecs else {}
    computed: list[tuple[Job, JobMatch, int | None, dict]] = []
    for job, match in rows:
        vector = job_vecs.get(job.id)
        similarity = rag_service.similarity(vector, fact_vecs) if vector is not None else None
        score, details = score_job(job, views, today, feedback, similarity)
        details["features"] = preference_model.features(details.get("parts", {}), details.get("similarity"),
                                                        job.apply_manually)
        if match is None:
            match = JobMatch(job_id=job.id)
            session.add(match)
        match.score = score
        match.has_blockers = bool(details["blockers"])
        match.scoring_version = SCORING_VERSION
        match.profile_fingerprint = fp
        match.job_hash = job_hash(job, vector is not None)
        match.details = details
        match.computed_at = now
        computed.append((job, match, score, details))
    session.flush()

    # Reward model from the user's decisions (uses stored features of every decided job).
    model = preference_model.train(_samples(session, feedback, outcomes))
    for _job, match, score, details in computed:
        if model is None or score is None or "features" not in details:
            continue
        adjust = model.adjustment(details["features"])
        details = dict(details)
        details["parts"] = {**details.get("parts", {}), "learned": adjust}
        if adjust:
            direction = "suits you" if adjust > 0 else "suits you less"
            details["reasons"] = [*details["reasons"],
                                  f"From your {model.labels} decisions so far, this kind of job {direction}: {adjust:+d}."]
        new = max(0, min(100, score + adjust))
        match.score = min(new, BLOCKER_CAP) if details["blockers"] else new
        match.details = details
    session.commit()
    return len(rows)


def _samples(session: Session, feedback: Feedback, outcomes: dict[str, str]) -> list[tuple[list[float], int, float]]:
    """Training data: (features, reward 0/1, weight) for every job the user decided on."""
    decided = feedback.decided
    if not decided:
        return []
    rows = session.scalars(select(JobMatch).where(JobMatch.job_id.in_(list(decided))))
    samples = []
    for row in rows:
        features = (row.details or {}).get("features")
        if not features:
            continue
        status, _ = decided[row.job_id]
        if status in NEGATIVE:
            samples.append((features, 0, 1.0))
        else:
            outcome = outcomes.get(row.job_id)
            weight = 3.0 if outcome in ("interview", "offer", "accepted") else 2.0 if status == "applied" else 1.0
            samples.append((features, 1, weight))
    return samples


def matches_for(session: Session, job_ids: list[str]) -> dict[str, JobMatch]:
    if not job_ids:
        return {}
    return {m.job_id: m for m in session.scalars(select(JobMatch).where(JobMatch.job_id.in_(job_ids)))}
