import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.middleware.error_handler import ErrorHandlerMiddleware
from src.middleware.jwt_auth import JwtAuthMiddleware
from src.routers import health, auth, profile, api_keys, sessions, invites, billing, notifications, tenant_params, telegram_auth

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("tenant-auth")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Tenant-Auth starting on %s:%s", settings.host, settings.port)
    yield
    logger.info("Tenant-Auth shutting down")


app = FastAPI(
    title="Tenant Auth Service",
    version="0.1.0",
    description="Authentication and tenant management microservice for AvitoSystem",
    lifespan=lifespan,
)

# Middleware (order matters: outermost = first to run)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(JwtAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(api_keys.router)
app.include_router(sessions.router)
app.include_router(invites.router)
app.include_router(billing.router)
app.include_router(notifications.router)
app.include_router(tenant_params.router)
app.include_router(telegram_auth.router)
