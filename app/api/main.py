from __future__ import annotations
from fastapi import FastAPI

app = FastAPI(title="Dream Assistant API")

@app.get("/health")
def health():
    return {"status": "ok"}
