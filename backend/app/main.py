"""FastAPI application factory and local entry point.

Run locally (binds to 127.0.0.1 by default):

    .venv\\Scripts\\python.exe -m app.main
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.adapters.web_fetch import SafeFetcher
from app.api import applications, auth, documents, extras, feeds, health, integrations, job_alerts, jobs, profile, system
from app.core.config import Settings, get_settings
from app.core.errors import AppError, error_body, install_error_handlers
from app.core.paths import ensure_data_dirs
from app.persistence.db import make_session_factory, prepare_database
from app.services import alert_service, backup_service, feed_service, integration_service
from app.services.storage import FileStore

logger = logging.getLogger("duuniscript")

UPLOAD_PATHS = {"/api/v1/documents", "/api/v1/job-alerts/emails", "/api/v1/jobs/from-screenshots"}
MULTIPART_OVERHEAD = 64 * 1024


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ensure_data_dirs(settings.app_data_dir)
        engine = prepare_database(settings)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        app.state.store = FileStore(settings.app_data_dir)
        if not hasattr(app.state, "fetcher"):
            app.state.fetcher = SafeFetcher(timeout_seconds=settings.url_import_timeout_seconds)
        if not hasattr(app.state, "feed_fetcher"):
            app.state.feed_fetcher = SafeFetcher(timeout_seconds=settings.feed_timeout_seconds)
        if not hasattr(app.state, "llm"):
            from app.services.llm import OllamaProvider

            app.state.llm = OllamaProvider(settings)
        from app.services import match_service as _match

        _match._APP_LLM["llm"] = app.state.llm
        if not hasattr(app.state, "integrations"):
            app.state.integrations = integration_service.Integrations(settings)
        if not hasattr(app.state, "mailbox_factory"):
            # A connected Gmail account is used instead of IMAP; IMAP stays as the fallback.
            app.state.mailbox_factory = lambda: (
                app.state.integrations.gmail_mailbox() or alert_service.make_mailbox(settings)
            )
        timer = None
        if settings.mail_sync_interval_minutes:

            def check_mailbox() -> None:
                integrations = app.state.integrations
                mailbox = app.state.mailbox_factory()
                if mailbox is not None:
                    with app.state.session_factory() as session:
                        try:
                            alert_service.sync_mailbox(session, app.state.store, mailbox, settings, actor="system")
                            integration_service.record_sync(session, "google", None)
                        except AppError as exc:
                            integration_service.record_sync(session, "google", exc.message)
                university = integrations.graph_mailbox()
                if university is not None:
                    with app.state.session_factory() as session:
                        try:
                            alert_service.sync_mailbox(session, app.state.store, university, settings, actor="system",
                                                       source_key=integration_service.MICROSOFT_SOURCE)
                            integration_service.record_sync(session, "microsoft", None)
                        except AppError as exc:
                            integration_service.record_sync(session, "microsoft", exc.message)

            timer = alert_service.AlertSyncTimer(check_mailbox, settings.mail_sync_interval_minutes)
            timer.start()
        feed_timer = None
        if settings.feed_sync_interval_minutes:

            def check_feeds() -> None:
                with app.state.session_factory() as session:
                    feed_service.sync_due(session, app.state.store, app.state.feed_fetcher, settings)

            feed_timer = alert_service.AlertSyncTimer(
                check_feeds, settings.feed_sync_interval_minutes, first_delay_seconds=90, name="feed-sync"
            )
            feed_timer.start()
        rag_timer = None
        if settings.rag_index_interval_minutes and settings.ollama_embed_model:
            from app.services import rag_service

            def index_rag() -> None:
                with app.state.session_factory() as session:
                    rag_service.index(session, app.state.llm)

            rag_timer = alert_service.AlertSyncTimer(
                index_rag, settings.rag_index_interval_minutes, first_delay_seconds=45, name="rag-index"
            )
            rag_timer.start()
        house_timer = None
        if settings.housekeeping_interval_minutes:
            from app.services import housekeeping, job_attachments

            def tidy() -> None:
                job_attachments.clean_pending(app.state.store)
                with app.state.session_factory() as session:
                    housekeeping.run(session, settings.job_archive_days)

            house_timer = alert_service.AlertSyncTimer(
                tidy, settings.housekeeping_interval_minutes, first_delay_seconds=120, name="housekeeping")
            house_timer.start()
        toast_timer = None
        if settings.desktop_notifications and settings.desktop_notify_interval_minutes:
            from app.services import desktop_notify

            def notify() -> None:
                with app.state.session_factory() as session:
                    desktop_notify.check(session, "http://127.0.0.1:8080")

            toast_timer = alert_service.AlertSyncTimer(
                notify, settings.desktop_notify_interval_minutes, first_delay_seconds=150, name="desktop-notify")
            toast_timer.start()
        backup_timer = None
        if settings.backup_interval_hours:

            def backup_if_due() -> None:
                if backup_service.due(settings):
                    backup_service.create(settings, reason="automatic")

            # Looks hourly; makes a backup when the newest one is older than the interval.
            backup_timer = alert_service.AlertSyncTimer(backup_if_due, 60, first_delay_seconds=300, name="backup")
            backup_timer.start()
        try:
            yield
        finally:
            for running in (timer, feed_timer, backup_timer, rag_timer, house_timer, toast_timer):
                if running is not None:
                    running.stop()
            engine.dispose()

    app = FastAPI(
        title="DuuniScript API",
        version=__version__,
        description="Local-first backend for DuuniScript. Binds to loopback by default.",
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.middleware("http")
    async def require_sign_in(request: Request, call_next):  # noqa: ANN001, ANN202
        path = request.url.path
        open_paths = ("/api/v1/auth/", "/api/v1/integrations/google/callback")  # callback: one-time state
        if request.method != "OPTIONS" and path.startswith("/api/v1/") and not path.startswith(open_paths):
            from app.api.auth import bearer
            from app.services import auth_service

            with app.state.session_factory() as session:
                # Once a passphrase exists it is never removed, so remember that.
                if not getattr(app.state, "auth_on", False):
                    app.state.auth_on = auth_service.password_set(session)
                if app.state.auth_on and auth_service.session_for(session, bearer(request)) is None:
                    return JSONResponse(
                        status_code=401, content=error_body("auth_required", "Sign in to DuuniScript first.")
                    )
        return await call_next(request)

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):  # noqa: ANN001, ANN202
        length = request.headers.get("content-length")
        is_upload = request.method == "POST" and request.url.path.rstrip("/") in UPLOAD_PATHS
        # Uploads get a larger limit; the store also enforces it while streaming,
        # so a missing or false Content-Length cannot bypass it.
        limit = settings.max_upload_bytes + MULTIPART_OVERHEAD if is_upload else settings.max_request_bytes
        if length is not None:
            try:
                too_large = int(length) > limit
            except ValueError:
                return JSONResponse(status_code=400, content=error_body("bad_request", "Invalid Content-Length."))
            if too_large:
                return JSONResponse(
                    status_code=413, content=error_body("request_too_large", "Request body is too large.")
                )
        return await call_next(request)

    # Added last, so it is the outermost layer: error and sign-in responses carry CORS headers too.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", "Authorization"],
        expose_headers=["Content-Disposition"],
    )

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(integrations.router)
    app.include_router(profile.router)
    app.include_router(documents.router)
    app.include_router(jobs.router)
    app.include_router(job_alerts.router)
    app.include_router(feeds.router)
    app.include_router(extras.router)
    app.include_router(applications.router)
    app.include_router(system.router)
    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    if not settings.is_loopback:
        logger.warning(
            "API_HOST is not a loopback address. The API has no authentication yet; "
            "do not expose it beyond this computer."
        )
    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    run()
