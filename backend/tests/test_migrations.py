from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.persistence.db import ALEMBIC_INI, MIGRATIONS_DIR, create_db_engine, run_migrations
from app.persistence.models import Base


def _config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'm.sqlite3').as_posix()}"


def test_upgrade_creates_tables(db_url: str) -> None:
    run_migrations(db_url)
    tables = set(inspect(create_engine(db_url)).get_table_names())
    assert {"user_profile", "profile_fact", "profile_evidence", "document", "audit_event", "alembic_version"} <= tables


def test_models_match_migrations(db_url: str) -> None:
    run_migrations(db_url)
    with create_engine(db_url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"Models and migrations differ; create a new Alembic revision: {diff}"


def test_downgrade_and_reupgrade(db_url: str) -> None:
    cfg = _config(db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(db_url)).get_table_names()) <= {"alembic_version"}
    command.upgrade(cfg, "head")


def test_0002_clears_dangling_document_references(db_url: str) -> None:
    cfg = _config(db_url)
    command.upgrade(cfg, "5b09faeb4cc8")
    engine = create_db_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO user_profile (id, display_name, created_at, updated_at) "
            "VALUES ('p1', 'Synthetic', '2026-01-01', '2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO profile_fact (id, profile_id, category, subject, value_text, verification_status, "
            "created_at, updated_at) VALUES ('f1', 'p1', 'skill', 's', 'v', 'unverified', '2026-01-01', '2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO profile_evidence (id, fact_id, document_id, source_type, verification_status, created_at) "
            "VALUES ('e1', 'f1', 'no-such-document', 'user_input', 'unverified', '2026-01-01')"
        ))
    engine.dispose()
    command.upgrade(cfg, "head")
    with create_db_engine(db_url).connect() as conn:
        assert conn.execute(text("SELECT document_id FROM profile_evidence WHERE id='e1'")).scalar() is None
        assert conn.execute(text("SELECT count(*) FROM profile_evidence")).scalar() == 1


def test_foreign_keys_enforced(db_url: str) -> None:
    run_migrations(db_url)
    engine = create_db_engine(db_url)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO profile_fact (id, profile_id, category, subject, value_text, "
                    "verification_status, created_at, updated_at) VALUES "
                    "('f1', 'missing-profile', 'skill', 's', 'v', 'unverified', '2026-01-01', '2026-01-01')"
                )
            )


def test_check_constraint_rejects_unknown_status(db_url: str) -> None:
    run_migrations(db_url)
    engine = create_db_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user_profile (id, display_name, created_at, updated_at) "
                "VALUES ('p1', 'Synthetic', '2026-01-01', '2026-01-01')"
            )
        )
    with engine.connect() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO profile_fact (id, profile_id, category, subject, value_text, "
                "verification_status, created_at, updated_at) VALUES "
                "('f1', 'p1', 'skill', 's', 'v', 'trusted', '2026-01-01', '2026-01-01')"
            )
        )
