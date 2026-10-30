import base64
import json
import traceback
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import llm, pipeline

STATIC = Path(__file__).resolve().parent.parent / "static"
MAX_PHOTOS, MAX_BYTES = 4, 8 * 1024 * 1024

app = FastAPI(title="Mouldproof")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.on_event("startup")
def startup():
    llm.discover_models()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/analyze")
async def analyze(story: str = Form(...), photos: list[UploadFile] = File(default=[])):
    images = []
    for f in photos[:MAX_PHOTOS]:
        raw = await f.read()
        if not raw:
            continue
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, f"{f.filename} is larger than 8 MB.")
        if not (f.content_type or "").startswith("image/"):
            raise HTTPException(415, f"{f.filename} isn't a photo.")
        images.append((base64.b64encode(raw).decode(), f.content_type))

    def stream():
        try:
            for ev in pipeline.run(images, story):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
