from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import anomalies, auth, predict, settings as settings_router, train, upload
from app.core.config import settings

app = FastAPI(
    title="Anomaly Detection System",
    description="Personalized anomaly detection in sequential data",
    version="0.1.0",
)

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
