import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.context import correlation_id
from app.db import engine
from app.routers import admin, admin_bootstrap, admin_intelligence, auth, campaigns, campaigns_public, conversations, csr_profiles, documents, donations, email_notifications, escalations, feed, inbox, notifications, onboarding, opportunities, orgs, pan_verification, payments, profiles, projects, proposals, public, social_receipts

log = logging.getLogger("vitainspire")


def create_app() -> FastAPI:
    app = FastAPI(title="Imparency API", version="0.1.0")

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        # Honour an upstream id if one is supplied; otherwise mint one. Stored for audit rows and logs.
        incoming = request.headers.get("x-request-id")
        cid = incoming if incoming and len(incoming) <= 64 else str(uuid.uuid4())
        token = correlation_id.set(cid)
        try:
            response = await call_next(request)
        finally:
            correlation_id.reset(token)
        response.headers["x-request-id"] = cid
        return response

    @app.exception_handler(RuntimeError)
    async def internal_error(request: Request, exc: RuntimeError):
        log.error("internal error cid=%s path=%s: %s", correlation_id.get(), request.url.path, exc)
        return JSONResponse({"detail": "Internal error", "request_id": correlation_id.get()}, status_code=500)

    @app.get("/health")
    def health() -> dict:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(orgs.router)
    app.include_router(profiles.router)
    app.include_router(csr_profiles.router)
    app.include_router(projects.router)
    app.include_router(onboarding.router)
    app.include_router(documents.router)
    app.include_router(pan_verification.router)
    app.include_router(donations.router)
    app.include_router(opportunities.router)
    app.include_router(opportunities.ngo_router)
    app.include_router(proposals.router)
    app.include_router(campaigns.router)
    app.include_router(campaigns_public.router)
    app.include_router(conversations.router)
    app.include_router(inbox.router)
    app.include_router(notifications.router)
    app.include_router(email_notifications.router)
    app.include_router(escalations.router)
    app.include_router(payments.router)
    app.include_router(social_receipts.router)
    app.include_router(social_receipts.router_receipts)
    app.include_router(public.router)
    app.include_router(feed.router)
    app.include_router(feed.geocode_router)
    app.include_router(admin.router)
    app.include_router(admin_bootstrap.router)
    app.include_router(admin_intelligence.router)
    return app


app = create_app()
