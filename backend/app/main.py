from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import upload, train, predict, results

app = FastAPI(title="Anomaly Detection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://anomaly-detection.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api/v1")
app.include_router(train.router, prefix="/api/v1")
app.include_router(predict.router, prefix="/api/v1")
app.include_router(results.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
