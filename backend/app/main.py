import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import anomalies, auth, predict, settings as settings_router, train, upload
from app.core.config import DEFAULT_JWT_SECRET, settings
from app.core.limiter import limiter

logger = logging.getLogger(__name__)

if settings.JWT_SECRET == DEFAULT_JWT_SECRET:
    logger.warning(
        "JWT_SECRET is using the default placeholder value -- set a real secret "
        "via the JWT_SECRET env var before this is reachable outside localhost."
    )

app = FastAPI(
    title="Anomaly Detection System",
    description="Personalized anomaly detection in sequential data",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(train.router)
app.include_router(predict.router)
app.include_router(anomalies.router)
app.include_router(settings_router.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
