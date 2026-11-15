"""Retrieval (the "R" in RAG): local embeddings of verified facts and jobs.

Uses the local embedding model in Ollama (``OLLAMA_EMBED_MODEL``, e.g. the multilingual
bge-m3), so nothing leaves this computer. Vectors are stored in the ``embedding`` table and
recomputed only when the text changes.

What it is used for:
- **Match score:** how close a job's posting is in meaning to your verified facts (a job that
  asks for "analytics" matches "SPSS survey analysis" even without shared words).
- **Drafts and AI wording:** the verified facts most relevant to a job are retrieved and given
  to the drafting code and to the local model. Only verified facts are indexed, so retrieval can
  never bring in an unverified claim.
"""

from __future__ import annotations

import hashlib
import math
import struct
import threading

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.persistence.models import Embedding, Job, ProfileFact, VerificationStatus, utcnow
from app.services.profile_service import get_profile

BATCH = 16
MAX_JOB_CHARS = 2000
_LOCK = threading.Lock()


def _hash(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()


def pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def fact_text(fact: ProfileFact) -> str:
    return f"{fact.category.replace('_', ' ')}: {fact.subject}. {fact.value_text}"[:2000]


def job_text(job: Job) -> str:
    return f"{job.title} at {job.company}. {job.location or ''}\n{(job.description or '')[:MAX_JOB_CHARS]}"


def _verified(session: Session) -> list[ProfileFact]:
    profile = get_profile(session)
    if profile is None:
        return []
    return list(session.scalars(select(ProfileFact).where(
        ProfileFact.profile_id == profile.id, ProfileFact.verification_status == VerificationStatus.VERIFIED.value)))


def index(session: Session, llm, max_jobs: int = 5000) -> dict:  # noqa: ANN001
    """Embed new or changed verified facts and jobs. Safe to call often; does nothing without the model."""
    if llm is None or not llm.embeddings_available():
        return {"facts": 0, "jobs": 0, "available": False}
    model = llm.embed_model
    with _LOCK:
        existing = {(e.kind, e.ref_id): e for e in session.scalars(select(Embedding))}
        facts = _verified(session)
        fact_ids = {f.id for f in facts}
        # Facts no longer verified (or deleted) leave the index.
        stale = [e.id for (kind, ref), e in existing.items() if kind == "fact" and ref not in fact_ids]
        if stale:
            session.execute(delete(Embedding).where(Embedding.id.in_(stale)))
        todo: list[tuple[str, str, str]] = []
        for fact in facts:
            text = fact_text(fact)
            row = existing.get(("fact", fact.id))
            if row is None or row.text_hash != _hash(text, model):
                todo.append(("fact", fact.id, text))
        jobs = session.scalars(select(Job).where(Job.hidden.is_(False)).order_by(Job.first_seen_at.desc()).limit(max_jobs))
        for job in jobs:
            text = job_text(job)
            row = existing.get(("job", job.id))
            if row is None or row.text_hash != _hash(text, model):
                todo.append(("job", job.id, text))
        done = {"fact": 0, "job": 0}
        for start in range(0, len(todo), BATCH):
            chunk = todo[start: start + BATCH]
            vectors = llm.embed([t for _, _, t in chunk])
            for (kind, ref, text), vector in zip(chunk, vectors, strict=False):
                row = existing.get((kind, ref))
                if row is None:
                    row = Embedding(kind=kind, ref_id=ref)
                    session.add(row)
                    existing[(kind, ref)] = row
                row.model, row.text_hash, row.dim = model, _hash(text, model), len(vector)
                row.vector, row.created_at = pack(vector), utcnow()
                done[kind] += 1
            session.commit()
        session.commit()
        return {"facts": done["fact"], "jobs": done["job"], "available": True}


def fact_vectors(session: Session, model: str | None) -> dict[str, list[float]]:
    if not model:
        return {}
    ids = {f.id for f in _verified(session)}
    rows = session.scalars(select(Embedding).where(Embedding.kind == "fact", Embedding.model == model))
    return {r.ref_id: unpack(r.vector) for r in rows if r.ref_id in ids}


def job_vectors(session: Session, model: str | None, job_ids: list[str] | None = None) -> dict[str, list[float]]:
    if not model:
        return {}
    query = select(Embedding).where(Embedding.kind == "job", Embedding.model == model)
    if job_ids is not None:
        query = query.where(Embedding.ref_id.in_(job_ids))
    return {r.ref_id: unpack(r.vector) for r in session.scalars(query)}


def similarity(job_vector: list[float], facts: dict[str, list[float]], top: int = 5) -> float | None:
    """Mean of the closest facts' cosine similarity: how near the job is to the profile."""
    if not facts:
        return None
    sims = sorted((cosine(job_vector, v) for v in facts.values()), reverse=True)[:top]
    return sum(sims) / len(sims)


def relevant_facts(session: Session, llm, job: Job, k: int = 8) -> list[tuple[str, float]]:  # noqa: ANN001
    """Verified fact IDs closest in meaning to the job, best first (empty without the model)."""
    if llm is None or not llm.embeddings_available():
        return []
    facts = fact_vectors(session, llm.embed_model)
    if not facts:
        return []
    vector = job_vectors(session, llm.embed_model, [job.id]).get(job.id)
    if vector is None:
        vector = llm.embed([job_text(job)])[0]
    ranked = sorted(((fid, cosine(vector, v)) for fid, v in facts.items()), key=lambda p: -p[1])
    return ranked[:k]


def status(session: Session, llm) -> dict:  # noqa: ANN001
    model = llm.embed_model if llm else None
    count = lambda kind: len(list(session.scalars(select(Embedding.id).where(  # noqa: E731
        Embedding.kind == kind, Embedding.model == model)))) if model else 0
    return {"model": model, "available": bool(llm and llm.embeddings_available()),
            "facts_indexed": count("fact"), "jobs_indexed": count("job")}
