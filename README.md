# sd-image-api

A minimal, general-purpose image generation API that wraps [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) and exposes it over HTTP with full OpenAPI documentation.

## Stack

- **[stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp)** — fast C++ inference engine, no Python runtime required
- **[FastAPI](https://fastapi.tiangolo.com/)** — async HTTP layer with auto-generated OpenAPI spec + Swagger UI
- **Docker Compose** — one-command deployment

## Quick Start

### 1. Place a model

Download a GGUF or safetensors model and drop it in `./models/`:

```bash
# Example: download a GGUF model
wget -O models/model.gguf https://example.com/your-model.gguf
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set SD_MODEL to your model filename
```

### 3. Run (CPU)

```bash
docker compose up
```

### 3a. Run (NVIDIA GPU)

```bash
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up
```

## API

### Swagger UI

Open [http://localhost:8765/docs](http://localhost:8765/docs)

### OpenAPI spec

```bash
curl http://localhost:8765/openapi.json
```

### Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Check API + sd-server status |
| `GET` | `/models` | List available models |
| `GET` | `/samplers` | List available samplers |
| `POST` | `/generate` | Generate image, return base64 |
| `POST` | `/generate/file` | Generate image, save to `./outputs/` |
| `POST` | `/generate/batch` | Batch job (background), returns job ID |
| `GET` | `/jobs/{job_id}` | Poll batch job status |

### Generate an image

```bash
curl -X POST http://localhost:8765/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "tropical beach at sunset, photorealistic",
    "negative_prompt": "blurry, low quality",
    "width": 512,
    "height": 512,
    "steps": 20,
    "cfg_scale": 7.5,
    "sampler_name": "euler",
    "seed": -1
  }' | jq -r '.image_base64' | base64 -d > output.png
```

### Save to file

```bash
curl -X POST http://localhost:8765/generate/file \
  -H "Content-Type: application/json" \
  -d '{"prompt": "mountain landscape, oil painting style"}' | jq .filename
# → "img_20260331_143022_abc123.png" (saved in ./outputs/)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SD_MODEL` | `model.gguf` | Model filename inside `./models/` |
| `SD_SERVER_URL` | `http://sd-server:1234` | sd-server base URL (auto-set in compose) |
| `API_HOST` | `0.0.0.0` | Bind address — `0.0.0.0` makes it accessible on Tailscale |
| `API_PORT` | `8765` | Listen port |
| `OUTPUT_DIR` | `./outputs` | Where `/generate/file` saves PNGs |

## Tailscale / Tailnet access

Since `API_HOST` defaults to `0.0.0.0`, the API is reachable at your machine's Tailscale IP on port `8765`. No extra configuration needed.

## Development (without Docker)

```bash
pip install -r requirements.txt

# Start sd-server separately (see stable-diffusion.cpp releases for binaries)
./sd-server --listen-ip 0.0.0.0 --listen-port 1234 -m ./models/model.gguf &

# Start API
SD_SERVER_URL=http://localhost:1234 python main.py
```
