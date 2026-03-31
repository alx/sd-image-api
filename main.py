import base64
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

SD_SERVER_URL = os.getenv("SD_SERVER_URL", "http://localhost:1234")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8765"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="sd-image-api",
    description="General-purpose image generation API backed by stable-diffusion.cpp",
    version="1.0.0",
    contact={"url": "https://github.com/alx/sd-image-api"},
    license_info={"name": "MIT"},
)

# In-memory job store
jobs: dict[str, dict] = {}


# --- Schemas ---

class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt describing the image")
    negative_prompt: str = Field("", description="Things to avoid in the image")
    width: int = Field(512, ge=64, le=2048, description="Image width in pixels")
    height: int = Field(512, ge=64, le=2048, description="Image height in pixels")
    steps: int = Field(20, ge=1, le=150, description="Number of diffusion steps")
    cfg_scale: float = Field(7.5, ge=1.0, le=30.0, description="Classifier-free guidance scale")
    sampler_name: str = Field("euler", description="Sampling method")
    seed: int = Field(-1, description="Seed (-1 = random)")
    batch_size: int = Field(1, ge=1, le=4, description="Number of images to generate")


class GenerateResponse(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded PNG image")
    seed: int
    generation_time: float = Field(..., description="Generation time in seconds")


class GenerateFileResponse(BaseModel):
    filename: str
    path: str
    seed: int
    generation_time: float


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int = 0
    total: int = 0
    results: list[str] = Field(default_factory=list, description="Saved filenames")
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    api: Literal["ok"]
    sd_server: Literal["ok", "unreachable"]
    sd_server_url: str


# --- Helpers ---

async def call_txt2img(req: GenerateRequest) -> tuple[list[str], int]:
    """Call sd-server /sdapi/v1/txt2img, return (list_of_base64_images, seed)."""
    payload = {
        "prompt": req.prompt,
        "negative_prompt": req.negative_prompt,
        "width": req.width,
        "height": req.height,
        "steps": req.steps,
        "cfg_scale": req.cfg_scale,
        "sampler_name": req.sampler_name,
        "seed": req.seed,
        "batch_size": req.batch_size,
    }
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            resp = await client.post(f"{SD_SERVER_URL}/sdapi/v1/txt2img", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(502, detail=f"Cannot reach sd-server at {SD_SERVER_URL}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, detail=f"sd-server error: {e.response.text}")

    data = resp.json()
    images = data.get("images", [])
    seed = data.get("info", {}).get("seed", -1) if isinstance(data.get("info"), dict) else -1
    return images, seed


def save_image(b64: str, prefix: str = "img") -> tuple[str, str]:
    """Decode base64 PNG and save to OUTPUT_DIR. Returns (filename, abs_path)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6]
    filename = f"{prefix}_{ts}_{uid}.png"
    dest = OUTPUT_DIR / filename
    dest.write_bytes(base64.b64decode(b64))
    return filename, str(dest)


# --- Routes ---

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    sd_status = "unreachable"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{SD_SERVER_URL}/sdapi/v1/sd-models")
            if r.status_code < 500:
                sd_status = "ok"
    except Exception:
        pass
    overall = "ok" if sd_status == "ok" else "degraded"
    return HealthResponse(status=overall, api="ok", sd_server=sd_status, sd_server_url=SD_SERVER_URL)


@app.get("/models", tags=["System"])
async def list_models():
    """List models available in sd-server."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{SD_SERVER_URL}/sdapi/v1/sd-models")
            r.raise_for_status()
            return r.json()
        except httpx.ConnectError:
            raise HTTPException(502, detail=f"Cannot reach sd-server at {SD_SERVER_URL}")


@app.get("/samplers", tags=["System"])
async def list_samplers():
    """List available samplers."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{SD_SERVER_URL}/sdapi/v1/samplers")
            r.raise_for_status()
            return r.json()
        except httpx.ConnectError:
            raise HTTPException(502, detail=f"Cannot reach sd-server at {SD_SERVER_URL}")


@app.post("/generate", response_model=GenerateResponse, tags=["Generation"])
async def generate(req: GenerateRequest):
    """Generate image(s) from a text prompt. Returns base64-encoded PNG."""
    t0 = time.time()
    images, seed = await call_txt2img(req)
    if not images:
        raise HTTPException(500, detail="sd-server returned no images")
    return GenerateResponse(
        image_base64=images[0],
        seed=seed,
        generation_time=round(time.time() - t0, 2),
    )


@app.post("/generate/file", response_model=GenerateFileResponse, tags=["Generation"])
async def generate_file(req: GenerateRequest):
    """Generate an image and save it to disk. Returns filename and path."""
    t0 = time.time()
    images, seed = await call_txt2img(req)
    if not images:
        raise HTTPException(500, detail="sd-server returned no images")
    filename, path = save_image(images[0])
    return GenerateFileResponse(
        filename=filename,
        path=path,
        seed=seed,
        generation_time=round(time.time() - t0, 2),
    )


@app.post("/generate/batch", response_model=JobStatus, status_code=202, tags=["Generation"])
async def generate_batch(requests: list[GenerateRequest], background_tasks: BackgroundTasks):
    """Submit a list of generation requests as a background job."""
    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "queued", "progress": 0, "total": len(requests), "results": [], "errors": []}

    async def run_batch():
        jobs[job_id]["status"] = "running"
        for req in requests:
            try:
                images, _ = await call_txt2img(req)
                if images:
                    filename, _ = save_image(images[0])
                    jobs[job_id]["results"].append(filename)
            except Exception as e:
                jobs[job_id]["errors"].append(str(e))
            jobs[job_id]["progress"] += 1
        jobs[job_id]["status"] = "completed" if not jobs[job_id]["errors"] else "failed"

    background_tasks.add_task(run_batch)
    return JobStatus(job_id=job_id, **jobs[job_id])


@app.get("/jobs/{job_id}", response_model=JobStatus, tags=["Generation"])
async def get_job(job_id: str):
    """Poll the status of a background batch job."""
    if job_id not in jobs:
        raise HTTPException(404, detail="Job not found")
    return JobStatus(job_id=job_id, **jobs[job_id])


# --- Entrypoint ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)
